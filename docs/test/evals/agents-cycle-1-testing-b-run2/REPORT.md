# Agent eval report: testing mode

Run 2026-10-10 02:31 UTC against http://127.0.0.1:8714. 121 items. mode already testing

Pass 87, fail 32, error 2, pending 0 (pending = the route does not exist yet).

## Pass rate per agent

| Agent | Items | Pass | Fail | Error | Pending | Pass rate (of items that ran) |
|---|---|---|---|---|---|---|
| north | 20 | 15 | 5 | 0 | 0 | 75% |
| span | 26 | 26 | 0 | 0 | 0 | 100% |
| lumen | 39 | 16 | 23 | 0 | 0 | 41% |
| tally | 25 | 24 | 1 | 0 | 0 | 96% |
| memory | 11 | 6 | 3 | 2 | 0 | 55% |

## Pass rate per scorer

| Scorer | Scored | Pass | Fail | Pass rate |
|---|---|---|---|---|
| access | 18 | 17 | 1 | 94% |
| citation_present | 15 | 15 | 0 | 100% |
| cost | 17 | 17 | 0 | 100% |
| egress_clean | 44 | 44 | 0 | 100% |
| figure_match | 19 | 14 | 5 | 74% |
| follow_up_edit | 7 | 0 | 7 | 0% |
| groundedness | 59 | 52 | 7 | 88% |
| latency_ms | 37 | 37 | 0 | 100% |
| loop_trace | 38 | 33 | 5 | 87% |
| structure | 2 | 1 | 1 | 50% |
| trace_complete | 29 | 26 | 3 | 90% |
| turn_expect | 22 | 14 | 8 | 64% |
| words | 73 | 68 | 5 | 93% |

## Cost and latency per agent

| Agent | Median ms | p95 ms | Calls | Tokens | USD (agent-runs) | Egress lines | Egress blocked |
|---|---|---|---|---|---|---|---|
| north | 19769 | 45721 | 34 | 300900 | 0.1292 | 48 | 1 |
| span | 16741 | 55868 | 61 | 230185 | 0.0733 | 89 | 0 |
| lumen | 120 | 48238 | 39 | 144115 | 0.0339 | 52 | 0 |
| tally | 9501 | 18681 | 23 | 100184 | 0.0322 | 42 | 0 |
| memory | 118 | 12908 | 5 | 13580 | 0.0043 | 5 | 0 |

## Worst items

- **NOR-01** (north, analyst, fail): Narrative file in; the process map has 6 steps and the four manual steps are flagged. -> words: missing 'Collect the exports'; missing 'Check cash against the administrator'; missing 'Collect manager statements'; missing 'Convert to SGD'; missing 'Review and approve'; missing 'Read the report'; structure: 0 steps, wanted 6; manual steps flagged [], wanted [1, 2, 3, 4]
- **NOR-04** (north, analyst, fail): Step 2 exception carries Entity B 12,400 USD (P32) as written in the narrative. -> figure_match: missing: 12400; words: missing 'Entity B'
- **NOR-08** (north, analyst, fail): Handover email adds the 3-to-4 hand-over (Mei Chen to Raj Patel by email) to the thread. -> words: missing 'Raj Patel'
- **NOR-10** (north, participant, fail): A participant (Sofia Reyes) cannot write into the signed intent of work. -> access: status 200, wanted 403
- **NOR-11** (north, analyst, fail): Controls from the narrative reach the SOP (the 5,000 USD cash tolerance). -> figure_match: missing: 5000
- **LUM-SP-01** (lumen, sponsor, fail): ER-06: on the Consume landing Lumen reads a figure through query_figure (Lumen's tools are registered on the talk route). -> loop_trace: answered by the rules, not the agent's loop (rules_only); trace_complete: Lumen: no context step; Lumen: no model step; Lumen: no guard step
- **LUM-SP-02** (lumen, approver, fail): LQ-1: why net worth moved is answered from why_moved, never a cause taken from a newsletter. -> groundedness: not from the program: 3.37, 180,000, 350,000, 384,000, 600,000, 3,187,000, 3,367,000, 100,038,000, 103,405,000
- **LUM-SP-03** (lumen, sponsor, fail): ER-12, A4: 'And for Entity B?' repeats the last question for Entity B, not a question about tile settings. -> groundedness: not from the program: 868,000, 875,200, 880,400, 1,148,200, 1,150,000, 2,300,000
- **LUM-04** (lumen, sponsor, fail): Asked for net worth by entity, the proposed tile's rows equal the universe for September 2026. -> figure_match: missing: 22875000, 63950000, 16580000
- **LUM-05** (lumen, sponsor, fail): Asked for cash by entity, the tile rows hold Entity B administrator 880,400 and trading export 868,000. -> figure_match: missing: 880400, 868000
- **LUM-06** (lumen, sponsor, fail): Follow-up "make it dots" edits the last tile (mark becomes point). -> follow_up_edit: fewer than two tiles proposed
- **LUM-07** (lumen, sponsor, fail): Follow-up "line in red" edits the last tile (red line); red, because MEM-02 teaches blue and the talk keeps it (EVT-20). -> follow_up_edit: fewer than two tiles proposed
- **LUM-08** (lumen, sponsor, fail): Follow-up "monthly not daily" edits the period of the last tile. -> follow_up_edit: fewer than two tiles proposed
- **LUM-09** (lumen, sponsor, fail): Follow-up "in SGD" edits the last tile to SGD (WMR 1.3412 at 30 Sep is the universe's rate). -> follow_up_edit: fewer than two tiles proposed
- **LUM-10** (lumen, sponsor, fail): A chain of edits keeps editing the same tile (bars, then dots, then blue) - one series, so a colour applies (ER-16). -> follow_up_edit: fewer than two tiles proposed
- **LUM-AQ-01** (lumen, sponsor, fail): EVT-13 (A7) the cash tile keeps the accounting and operational views apart; their sum 1,748,400 is never a figure. -> figure_match: missing: 880400, 868000
- **LUM-AQ-02** (lumen, sponsor, fail): EVT-11 (A4) a chain on bars by status keeps editing one tile; dots by status are one series, so blue applies. -> follow_up_edit: fewer than two tiles proposed; loop_trace: answered by the rules, not the agent's loop (rules_only)
- **LUM-AQ-03** (lumen, sponsor, fail): LT-1 / LT-5 (A4, A2) "line in blue" on net worth by month gives a blue line, made by the loop's propose_tile_edit. -> follow_up_edit: fewer than two tiles proposed; loop_trace: answered by the rules, not the agent's loop (rules_only); trace_complete: no loop trace for this item
- **LUM-AQ-04** (lumen, sponsor, fail): LT-2 (A4) "last 12 months" keeps 12 month-ends (the SQL keeps dates after max minus 12 months, not from it). -> turn_expect: turn 2: missing 'for the last 12 months'; turn 2: missing '> (select max('
- **LUM-AQ-05** (lumen, sponsor, fail): LT-4 / EVT-12 (A15) "by entity" on a tile already split by entity says so plainly; no table or column names. -> turn_expect: turn 2: missing 'already split by entity'

## Slowest items

- LUM-SP-03: 59449 ms
- SPA-SP-03: 57542 ms
- SPA-06: 55868 ms
- SPA-INJ-02: 51528 ms
- LUM-SP-01: 48238 ms

## Draft intents to delete by hand

The North items started these intents and no product route deletes a draft yet. Delete them by hand (or cancel each one) so they do not crowd the Intent Centre:

- ini-8e6fdca024015df89e2b6819ad163381
- ini-068ecb473d63365a5671e2ea782e731a
- ini-b8b8e296fa5a9a6e72987ab03e3e7e96
- ini-5e3dfebc06064af22570e7d76cade390
- ini-fff9ecd6bbb2cf1e639f6141699884ac
- ini-d4ebbca1c1c04f78d35fdb7b1bcbfa91
- ini-769e182545a78847d2801d2e4b435ba5
- ini-1e505ef36bafbdb8c0154de318564d58
- ini-4373e63bd9684ae3c8ae10090a559f72
- ini-7a49d39ce78e3d07ae27fd2efa5830ac
- ini-afbd945607d305bc79244a0d6d5f4074
- ini-932c3b32e14f393e1676c5be26d408fc
- ini-19aa1e8b18c6ebcb6272f5d17714f681
- ini-a6113550b70495cd26dd82110a225c5b
- ini-5b3eb866eeef0e2b78c50f26d696ff61
- ini-7c721287ab21586f6f2c83bb31b8bd9b
- ini-c75dc4882374abf75da2d36eacb1d9b8
- ini-b8646048e27bccb86e80e77c556d1989
- ini-ec2c267a0bbebe697bcb79c4dfa84492

Per-item request, response, scores, trace id, cost and latency: `items/<id>.json`.
