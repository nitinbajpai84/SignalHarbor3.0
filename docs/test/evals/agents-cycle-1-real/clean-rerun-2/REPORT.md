# Agent eval report: real mode

Run 2026-10-09 17:56 UTC against http://127.0.0.1:8715. 6 items. mode switched testing -> real

Pass 2, fail 4, error 0, pending 0 (pending = the route does not exist yet).

## Pass rate per agent

| Agent | Items | Pass | Fail | Error | Pending | Pass rate (of items that ran) |
|---|---|---|---|---|---|---|
| north | 2 | 1 | 1 | 0 | 0 | 50% |
| lumen | 2 | 0 | 2 | 0 | 0 | 0% |
| tally | 1 | 0 | 1 | 0 | 0 | 0% |
| memory | 1 | 1 | 0 | 0 | 0 | 100% |

## Pass rate per scorer

| Scorer | Scored | Pass | Fail | Pass rate |
|---|---|---|---|---|
| access | 1 | 1 | 0 | 100% |
| citation_present | 1 | 1 | 0 | 100% |
| egress_clean | 1 | 1 | 0 | 100% |
| figure_match | 2 | 0 | 2 | 0% |
| follow_up_edit | 2 | 0 | 2 | 0% |
| groundedness | 2 | 2 | 0 | 100% |
| turn_expect | 1 | 1 | 0 | 100% |
| words | 2 | 1 | 1 | 50% |

## Cost and latency per agent

| Agent | Median ms | p95 ms | Calls | Tokens | USD (agent-runs) | Egress lines | Egress blocked |
|---|---|---|---|---|---|---|---|
| north | 28627 | 32939 | 7 | 103015 | - | 7 | 0 |
| lumen | 58021 | 61358 | 24 | 129422 | - | 24 | 0 |
| tally | 28178 | 28178 | 0 | 0 | - | 6 | 0 |
| memory | 9097 | 9097 | 2 | 4403 | - | 3 | 1 |

## Worst items

- **NOR-04** (north, analyst, fail): Step 2 exception carries Entity B 12,400 USD (P32) as written in the narrative. -> figure_match: missing: 12400; words: missing 'Entity B'
- **LUM-08** (lumen, sponsor, fail): Follow-up "monthly not daily" edits the period of the last tile. -> follow_up_edit: fewer than two tiles proposed
- **LUM-10** (lumen, sponsor, fail): A chain of edits keeps editing the same tile (bars, then dots, then blue). -> follow_up_edit: colour None, wanted blue
- **TAL-06** (tally, participant, fail): P17 real breach - Harborview Semiconductor 2,368,000 of 41,200,000 = 5.75%, over the 5% limit by 308,000, cause real breach. -> figure_match: missing: 308000

## Slowest items

- LUM-10: 61358 ms
- LUM-08: 54685 ms
- NOR-04: 32939 ms
- TAL-06: 28178 ms
- NOR-INJ-01: 24315 ms

## Draft intents to delete by hand

The North items started these intents and no product route deletes a draft yet. Delete them by hand (or cancel each one) so they do not crowd the Intent Centre:

- ini-a35d12f0dc089bc040fd3bbe02e4b28c
- ini-00e3c838c98795cdc2a7b5a0a14da259

Per-item request, response, scores, trace id, cost and latency: `items/<id>.json`.
