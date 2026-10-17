# W1b build: Operate and control, cards 51 to 100

Cards in this slice (Operate and control, no priority): 10. **Built: 8. Not built: 2.** Synthetic data only (Evergreen Office, `tests/v1/fixtures/office6m`).

First round (2 built): `trade_breaks` and `fx_mtm`. Second round, after the Wave 2 model (A32 to A47) and the treasury, assets and controls readers: six more cards built on the new readers. Cards 57 and 63 stay unbuilt.

Files written: `packs/family_office/1/recipes/operate.yaml` (stubs `position_break`, `unsettled_trades`, `source_quality` filled; `fx_mtm`, `trade_breaks`, `break_age`, `unrecognised_files`, `feed_mapping` added), 21 signals `packs/family_office/1/signals/uc8-trades-vs-admin-*.yaml` (5), `uc-056-custrecon-*` (2), `uc-058-settle-*` (2), `uc-059-breakage-*` (2), `uc-060-docinbox-*` (3), `uc-061-dqscore-*` (2), `uc-062-fxlife-*` (4), `uc-099-newfeed-*` (1), `packs/family_office/1/builds/operate-51.yaml`, `tests/v1/test_w1b_operate.py`, this page.

## Test result

`python -m pytest tests/v1/test_w1b_operate.py -q -p no:cacheprovider --basetemp=D:/Temp/pyt-w1b-op51` gives **28 passed, 0 failed** (about 30 s). With `test_w1_operate.py`, `test_w2_loader.py`, `test_v3_recipes.py`, `test_w1b_cash.py`, `test_w1b_office.py` and the three `test_w2_readers_*.py`: **160 passed, 0 failed**. `test_w1b_invest.py`, `test_w1b_report.py`, `test_w1_cash.py`, `test_w1_invest.py`, `test_v3_signals.py`, `test_seed_10uc.py` pass; two tests of `test_fixc_span_pack.py` (`uc6_rules...`, `uc6_model_design...`) fail with or without this change (checked with `operate.yaml` at HEAD).
The recipes run on the real pack readers: the office is copied to a dropbox and loaded by `v3_pack_readers.load_plane` (the `office` fixture of `test_w2_loader.py`), the recipe SQL is rendered by `v3_recipes.render`, checked with `v3_recipes.refusal` and its tie-out run. Every number is read from `answer_keys.yaml`, none is typed.

## Built

| Card | Recipe | Signals | Result against the key |
|---|---|---|---|
| 51 `uc8-trades-vs-admin` (ops_clerk) | `trade_breaks`; the FX leg is the existing `fx_confirmation_variance` (cash.yaml) | `-quantity-differs`, `-missing-at-administrator`, `-missing-at-desk` (problem, hold `accept_administrator_trades`), `-booked-twice` (needs), `-fx-confirmation-differs` (problem, hold `settle_forward`) | NWL T-20261002-003: desk 12,000, administrator 10,200, 75,870; HVS T-20261006-005 missing at the administrator, 592,000; T-20260602-005 booked twice; FXF-2026-002 variance 8,100 SGD. Tie-out ok |
| 56 `uc-056-custrecon` (ops_lead) | `position_break` (stub filled): the custodian's safekeeping statement (fields `custody_quantity`, `portfolio`, `custodian_note`) against the administrator's accounting position of the same portfolio and day | `-quantity-differs`, `-missing-one-side` (problem, hold `accept_administrator_positions`) | 20 holdings compared; Bay Street Utilities 40,000 against 41,250, -1,250, -60,062.50 USD, "Scrip dividend credited on 29 Sep..."; Redwood Pharma 40,000 against 39,600, +400, 18,940, "Transfer-out to a family brokerage account...". Tie-out ok |
| 58 `uc-058-settle` (ops_clerk) | `unsettled_trades` (stub filled) | `-failed` (problem, hold `release_trade_cash`), `-late` (needs) | BR2-20261002-001 Larkspur Health buy 5,000, 281,150, settle 6 Oct, 5 business days late, seller short delivery; BR2-20261007-002 Evermore Banking Group buy 10,000, 312,000, 9 Oct, 2 days, settlement instruction mismatch; chase Synthetic Broker Two; no cash booked. The five settled trades of the report stay settled. Tie-out ok |
| 59 `uc-059-breakage` (ops_lead) | `break_age` (new) | `-to-finance` (problem, no hold), `-open` (info) | All six open breaks with type, entity, subject, detection date and age (3, 3, 84, 47, 92, 64 business days); 4 open cash breaks; over five days: BRK-003, BRK-004. Tie-out ok |
| 60 `uc-060-docinbox` (ops_clerk) | `unrecognised_files` (new) | `-unrecognised` (problem, hold `load_inbox_file`), `-duplicate` (info), `-new` (needs) | 5 files: scan_0412.pdf (notices, duplicate), account_extract.xlsx (bank_statements, duplicate), INV-OIT-2610.pdf (invoices, new); IMG_2210.pdf refuse, data_export.xlsx hold and ask. Tie-out ok |
| 61 `uc-061-dqscore` (head_of_data) | `source_quality` (stub filled; formula changed to the card's: on time, added up, no manual fix) | `-fix-first` (problem, no hold), `-never-arrived` (needs) | All 12 sources: loads, passed, late or missing, did not add up, manual fixes and score exactly as the key (71.4 to 100); fix first administrator_cash. Tie-out ok (411 marked batches) |
| 62 `uc-062-fxlife` (ops_clerk) | `fx_mtm` | `-marked` (info), `-due-soon` (needs), `-confirmation-differs` and `-no-confirmation` (problem, hold `settle_forward`) | FXF-2026-002 mark 5,597.01, mismatch; USD to deliver 5,000,000; next value date 2026-12-15. Tie-out ok |
| 99 `uc-099-newfeed` (head_of_data) | `feed_mapping` (new) | `-in-doubt` (problem, hold `load_new_feed`) | 10 columns, 8 mapped with confidence, 80 percent, in doubt Value and Dt (with what each could be), 3 rows in the sample, not safe to go live. Tie-out ok |

Notes on the new recipes:
- `position_break` reads the statement (A46), not the custodian's daily file: the daily file agrees with the administrator on all 20 holdings, the statement does not. The holding is matched by name (the reader writes the security master's name). No tolerance is signed, so any difference is a break. The value is at the administrator's price of the day.
- `unsettled_trades`: the settlement reader keeps no cash for a failed trade (A45), so the report's amount is not on the row. The recipe values a trade with no cash at the custodian's price of the trade date (operational position, market value over quantity); this gives the key's 281,150 and 312,000. The as-at day is the latest day a file was received (13 Oct), as in `statement_timeliness`.
- `break_age` reads the register (exceptions of type `break`, A45). The register's type is the description before its first ";" (the reader writes "cash break; owner ..."). The three `cash_break` exceptions of the exception log are not counted again. "Older than five days" is the card's own question, shown as the column `over_five_business_days`, not a signed rule; the steward named no break-age rule. Same pattern as `fx_mtm`'s 30 days.
- `source_quality`: a statement that never arrived has no batch to mark. It is the expected statement still missing at the as-at day (TCB-B-USD July, Cedarpoint Opportunities II June), counted as one load of bank_statements or manager_statements that was late and did not add up, which is how the load log reports it. This gives the key's 84 and 60 loads.
- `feed_mapping` takes the mappings whose columns carry a confidence mark (a profiled new feed). The administrator's own drift proposal has no confidence and is left out. Safe to go live means the mapping is approved and no column is in doubt.
- `trade_breaks` was changed: a trade with status failed is left out. The settlement reader adds Broker Two's two failed buys as transactions. The administrator books no failed trade, so they would have shown as "missing at administrator". They belong to card 58.
- uc8 has an older build in `builds/legacy-office6m.yaml` (FX leg only, expects 8,100). `operate-51.yaml` carries the same id with the trade breaks added.

## Not built (2)

| Card | Not built because | Proved by | Needs |
|---|---|---|---|
| 57 `uc-057-pricecheck` | `market_data` still has no reader (no group took it), so no second price series is in `market_observations`. The 0.5 percent tolerance is the signed rule `price_tolerance_pct` (A46), and that rule is named but not signed. | `test_card57_...`, the guard `test_every_unread_kind_...[uc-057-pricecheck]`; `price_gap_pct` stays a stub (tested) | A reader for `market_data` writing a second series in `market_observations` (A46); `price_tolerance_pct` signed in `business_rules`; then `price_gap_pct`, held while the rule is unsigned |
| 63 `uc-063-cashcode` | A45 says an unexplained line is a bank line with no matching `reference` in the schedule, the ledger, the grants or a notice. The bank statement reader writes no `reference` and no `payee_name` on any bank line (0 confirmed movements carry either), so no line can be matched. Picking the three by their movement types (cheque, card_debit, transfer_in) would be an unsigned rule. | `test_card63_...` | The bank statement reader fills `cash_movements.reference` (and `payee_name`) from the statement's reference and counterparty columns; then `cash_code` (bank lines whose reference matches nothing, leaving out the bank's own fee and interest lines) |

The guard tests (`test_every_unread_kind_of_an_unbuilt_card_is_still_unread`) fail the day a card's missing reader is added. That is the day to build the card.

## Open points
- The callers that must honour the holds (`accept_administrator_trades`, `accept_administrator_positions`, `release_trade_cash`, `settle_forward`, `load_inbox_file`, `load_new_feed`) do not exist yet. This is the same open point as the top 50 (`build-operate.md` Needs 10).
- Cards 59 and 61 have an exception signal with no hold. Their stories are a handover to Finance and a score, so nothing waits on them.
- `fx_mtm` does not join the Trust's cash to compute the shortfall. The test shows that the two figures together give the key's number.
- Signals trigger on `figure_changed`, with one event per row of the figure (`build-operate.md` Needs 9).
- Outside these files: `tests/v1/test_e0a.py` and `tests/v1/test_d1.py` still count 50 tables (A47). Not touched here.
