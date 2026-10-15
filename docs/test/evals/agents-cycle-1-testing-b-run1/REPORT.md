# Agent eval report: testing mode

Run 2026-10-10 02:02 UTC against http://127.0.0.1:8714. 121 items. mode already testing

Pass 90, fail 29, error 2, pending 0 (pending = the route does not exist yet).

## Pass rate per agent

| Agent | Items | Pass | Fail | Error | Pending | Pass rate (of items that ran) |
|---|---|---|---|---|---|---|
| north | 20 | 18 | 2 | 0 | 0 | 90% |
| span | 26 | 26 | 0 | 0 | 0 | 100% |
| lumen | 39 | 16 | 23 | 0 | 0 | 41% |
| tally | 25 | 24 | 1 | 0 | 0 | 96% |
| memory | 11 | 6 | 3 | 2 | 0 | 55% |

## Pass rate per scorer

| Scorer | Scored | Pass | Fail | Pass rate |
|---|---|---|---|---|
| access | 18 | 18 | 0 | 100% |
| citation_present | 15 | 15 | 0 | 100% |
| cost | 17 | 17 | 0 | 100% |
| egress_clean | 44 | 44 | 0 | 100% |
| figure_match | 19 | 16 | 3 | 84% |
| follow_up_edit | 7 | 0 | 7 | 0% |
| groundedness | 59 | 52 | 7 | 88% |
| latency_ms | 37 | 37 | 0 | 100% |
| loop_trace | 38 | 32 | 6 | 84% |
| structure | 2 | 2 | 0 | 100% |
| trace_complete | 29 | 27 | 2 | 93% |
| turn_expect | 22 | 14 | 8 | 64% |
| words | 73 | 69 | 4 | 95% |

## Cost and latency per agent

| Agent | Median ms | p95 ms | Calls | Tokens | USD (agent-runs) | Egress lines | Egress blocked |
|---|---|---|---|---|---|---|---|
| north | 14560 | 78319 | 38 | 331351 | 0.1379 | 47 | 1 |
| span | 11154 | 40567 | 55 | 225754 | 0.0736 | 84 | 0 |
| lumen | 98 | 22433 | 37 | 134113 | 0.0329 | 47 | 0 |
| tally | 10444 | 25961 | 29 | 131570 | 0.043 | 50 | 0 |
| memory | 31 | 5206 | 4 | 9918 | 0.0032 | 4 | 0 |

## Worst items

- **NOR-08** (north, analyst, fail): Handover email adds the 3-to-4 hand-over (Mei Chen to Raj Patel by email) to the thread. -> words: missing 'Raj Patel'
- **LUM-SP-01** (lumen, sponsor, fail): ER-06: on the Consume landing Lumen reads a figure through query_figure (Lumen's tools are registered on the talk route). -> groundedness: not from the program: 868,000, 880,400, 1,148,200, 1,150,000, 2,300,000
- **LUM-SP-02** (lumen, approver, fail): LQ-1: why net worth moved is answered from why_moved, never a cause taken from a newsletter. -> groundedness: not from the program: 3.37, 180,000, 350,000, 384,000, 600,000, 3,187,000, 3,367,000, 100,038,000, 103,405,000
- **LUM-SP-03** (lumen, sponsor, fail): ER-12, A4: 'And for Entity B?' repeats the last question for Entity B, not a question about tile settings. -> words: none of: 880,400 / 880400; loop_trace: answered by the rules, not the agent's loop (rules_only)
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
- **LUM-AQ-06** (lumen, sponsor, fail): LQ-2 / LQ-9 (A3, A16) why net worth moved in September - Aug against Sep by entity, the change worked out by the program. -> words: none of: 3,367,000 / 3367000
- **LUM-AQ-09** (lumen, sponsor, fail): LT-6 / LT-7 (A15, A16) a new tile has a plain title with its currency, a true note, and the partial first month is said. -> turn_expect: turn 1: missing 'net worth per month (usd)'; turn 1: missing 'probably incomplete'
- **LUM-AQ-10** (lumen, sponsor, fail): lumen-memory-06 / -07 (A6) talk about how the report is run is answered in words, not as a tile edit or a table list. -> loop_trace: Lumen (done): context -> model -> guard; no tool call
- **MEM-01** (memory, sponsor, fail): A preference told to Lumen is still there in a new session. -> turn_expect: turn 1: missing 'remember'; turn 2: missing 'month'

## Slowest items

- NOR-08: 78319 ms
- LUM-SP-03: 61152 ms
- SPA-SP-03: 57152 ms
- NOR-01: 42898 ms
- SPA-07: 40567 ms

## Draft intents to delete by hand

The North items started these intents and no product route deletes a draft yet. Delete them by hand (or cancel each one) so they do not crowd the Intent Centre:

- ini-c85c8f53a5bdff1f16d1d947def750cb
- ini-1c989a947c13f08ae2a765b15bed0d66
- ini-87c057b2475e43f729c0502782a7a320
- ini-d1f33002427b824573e6a0b7cf544182
- ini-894e8c44f879077027760f9209160967
- ini-43570ed65b2dbdb58230b4c7b47c66cc
- ini-ea0abe0f72cd013ac20b687130002a8c
- ini-f08618befc405fdd6ba644cd91d28492
- ini-1549adceb3fa7f5ae42258995d2f64d9
- ini-124e8f0cfa92c4ed33e2888b9383c6a3
- ini-1e27a26c58af1f8f173af00a948d4393
- ini-e14e261f8cb0774ab669bfa1d3d9f46a
- ini-b4bca85d0f032f58ff4ae858de226f71
- ini-95c559d2e88cbd9b527730e35268e53b
- ini-1f02607b11fb8fb0ad35c89f08bfdae9
- ini-838d30e7b9f6eb0aec46a4837444be7c
- ini-6b4889a8eeaf3865fa14d44b0745f1c7
- ini-91933bb3077378a4aec49966e7dd1911
- ini-c6dfcbabb0eeba0d166c00b2ce6f5370

Per-item request, response, scores, trace id, cost and latency: `items/<id>.json`.
