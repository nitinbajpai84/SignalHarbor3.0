# Agent eval report: testing mode

Run 2026-10-10 02:53 UTC against http://127.0.0.1:8714. 121 items. mode already testing

Pass 82, fail 37, error 2, pending 0 (pending = the route does not exist yet).

## Pass rate per agent

| Agent | Items | Pass | Fail | Error | Pending | Pass rate (of items that ran) |
|---|---|---|---|---|---|---|
| north | 20 | 13 | 7 | 0 | 0 | 65% |
| span | 26 | 23 | 3 | 0 | 0 | 88% |
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
| figure_match | 19 | 15 | 4 | 79% |
| follow_up_edit | 7 | 0 | 7 | 0% |
| groundedness | 60 | 54 | 6 | 90% |
| latency_ms | 37 | 37 | 0 | 100% |
| loop_trace | 38 | 30 | 8 | 79% |
| structure | 2 | 1 | 1 | 50% |
| trace_complete | 29 | 27 | 2 | 93% |
| turn_expect | 22 | 14 | 8 | 64% |
| words | 73 | 65 | 8 | 89% |

## Cost and latency per agent

| Agent | Median ms | p95 ms | Calls | Tokens | USD (agent-runs) | Egress lines | Egress blocked |
|---|---|---|---|---|---|---|---|
| north | 12942 | 43764 | 38 | 274149 | 0.1202 | 47 | 2 |
| span | 11771 | 42216 | 59 | 220387 | 0.0708 | 90 | 0 |
| lumen | 65 | 26008 | 35 | 128733 | 0.0308 | 46 | 0 |
| tally | 11428 | 18861 | 23 | 110348 | 0.035 | 41 | 0 |
| memory | 89 | 12366 | 5 | 13717 | 0.0043 | 5 | 0 |

## Worst items

- **NOR-01** (north, analyst, fail): Narrative file in; the process map has 6 steps and the four manual steps are flagged. -> words: missing 'Collect the exports'; missing 'Check cash against the administrator'; missing 'Collect manager statements'; missing 'Convert to SGD'; missing 'Review and approve'; missing 'Read the report'; structure: 0 steps, wanted 6; manual steps flagged [], wanted [1, 2, 3, 4]
- **NOR-05** (north, analyst, fail): Owners removed from the narrative - North asks who owns the steps and does not make a name up. -> words: missing '?'
- **NOR-10** (north, participant, fail): A participant (Sofia Reyes) cannot write into the signed intent of work. -> access: status 200, wanted 403
- **NOR-11** (north, analyst, fail): Controls from the narrative reach the SOP (the 5,000 USD cash tolerance). -> figure_match: missing: 5000
- **SPA-06** (span, participant, fail): A change request from a participant stays a suggestion - the plan is not changed. -> words: none of: suggest / data team / head of data / waiting / data engineer / pending
- **SPA-07** (span, analyst, fail): Even for the data team, a change request waits as a pending change until accepted - the plan is unchanged. -> words: none of: pending / accept / change
- **LUM-SP-01** (lumen, sponsor, fail): ER-06: on the Consume landing Lumen reads a figure through query_figure (Lumen's tools are registered on the talk route). -> words: none of: 880,400 / 880400
- **LUM-SP-02** (lumen, approver, fail): LQ-1: why net worth moved is answered from why_moved, never a cause taken from a newsletter. -> groundedness: not from the program: 3.37, 180,000, 350,000, 384,000, 600,000, 3,187,000, 3,367,000, 100,038,000, 103,405,000
- **LUM-SP-03** (lumen, sponsor, fail): ER-12, A4: 'And for Entity B?' repeats the last question for Entity B, not a question about tile settings. -> words: none of: 880,400 / 880400
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

## Slowest items

- SPA-06: 50340 ms
- NOR-08: 43764 ms
- MX-SPA-ADMIN: 42216 ms
- NOR-04: 40678 ms
- SPA-SP-03: 38321 ms

## Draft intents to delete by hand

The North items started these intents and no product route deletes a draft yet. Delete them by hand (or cancel each one) so they do not crowd the Intent Centre:

- ini-676a42d486f9f4555ce323b7e195f1f7
- ini-e9f61d06e835bba49549b55d97e13d3c
- ini-cbd62c5511c39bfbe29869490b12af73
- ini-ef051e5d9bdbbde18c30d35f7ad61356
- ini-02886fee96bdc1565d2a8e2157632450
- ini-557753d050148affb0c9d633e737f273
- ini-e6a004fbb28ab7ce49e561657cb2463d
- ini-6e58e215a759dc95e6b876fa4fa27577
- ini-2651f148445df7ad5d2bd6b0a3c858ba
- ini-071b15082449aadb417c4ba9529cf6a1
- ini-7ed26316633833b9a961fd5b7c902054
- ini-d0854ae10177dbdbbbe64806f1e7f477
- ini-e590866c9dad3b58e0b98b12d25c6d24
- ini-f3494c9b948710763474553efee17fa2
- ini-02db2fd111cecf99baf4b3111fb5fb51
- ini-6a1a49f3f9f5bff7001c8bfbfd732d49
- ini-ffacd86ef083e394f535d37ddea956c3
- ini-21a88ecd3ed724479c417878915ef5a7
- ini-5ca0b7fb1bcc6fb94cdb588f14864c1e

Per-item request, response, scores, trace id, cost and latency: `items/<id>.json`.
