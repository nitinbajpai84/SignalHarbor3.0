# operations: run log, alerts, weekly check-ins, wall cards, one brainstorm (illustrative, synthetic)

Window 2026-07-01 to 2026-10-06 (98 days; 69 business days with files). Today is 2026-10-07; nothing is dated later than 2026-10-06.

## Files
| File | Grain | Shape |
|---|---|---|
| runs.json | one run per file per business day (1,035), oldest first | `{"runs": [{id, source, started, ended, on_time, rows, schema_ok, rules[{rule, passed, count}], marts_ready, sla_met, owner, status ok/late/failed}]}`. One run for each row of landing/file_arrival_log.csv; `id` is `run-<source>-<date>`; `status` is late when late_flag is Y, failed when schema_ok is N |
| alerts.json | six alerts | `{"alerts": [{id, kind, source, measure, owner, opened, state, by, at, note}]}` |
| weeks/2026-W<week>.json | one file per ISO week W27 to W41 (W41 still open) | week file: week_key, opens, closes, state, items[{id, by, kind ran/broke/thought, text, severity, count, amount, ref, fate, fate_reason, decided_by}], review, closed_at. `by` is a person id from master/people.csv (P07 Aaron Lyle, P14 Mei Ling Chong, P17 Harvey Rowley, P19 Rahul Mehta, P21 Amirul Hakim, P22 Natasha Wee) or `anonymous`; `decided_by` P48 is the reviewer |
| walls/treasury.json, performance.json, next_generation.json | one wall each | wall name, session kind, frozen, cards[{id, lane tracking/missing/watch/levers, q1 to q4 each {value, mark}, sealed, anonymous, author, placement fields}] |
| brainstorm_ideas.json | one brainstorm's idea cards | same card shape, lane levers |

## Notes
- Times are UTC in runs and alerts; owner is a name. A source is `<type>_<id>`: custodian C1 to C3, administrator A1 to A3, bank B01 to B08, index_provider IDX.
- Late and failed counts by source: administrator_A2 late 13, bank_B04 late 1, custodian_C1 late 1, custodian_C3 failed 1 (schema), all others on time.
- Monthly late counts in gold come from the landing log; this folder only restates it per run.
