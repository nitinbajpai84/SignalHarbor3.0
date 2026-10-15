# FIXB1 trade loader (UC8 blocker B1)

Landed: the trading export (daily CSV) and the administrator trade file (monthly Excel) now load into silver `transactions`, so `trade_vs_admin` has something to read.

Files
- `sh_platform/v1/trade_intake.py` (new): layout detection, mapping, batches, control totals, source_records, supersession, `load_folder`.
- `sh_platform/v1/e0c_load.py`: 5 lines appended at the end. `_load` is wrapped; a trade file goes to `trade_intake.dispatch`, anything else runs the old `_load` unchanged. Backup: `D:/Temp/bak-fixb1/e0c_load.py.orig`.
- `tests/v1/test_trade_intake.py`: 6 tests.

How it works
- Source system by type: trading export = `OMS`, administrator = `administrator` (what the trade check reads). Reused if the company has one, made if not.
- One `source_batches` row per file, control totals (administrator: "Trade rows" and gross per currency against the file footer; a mismatch rejects the file), one `source_records` row per file row (sheet, row, cell range), `transactions.source_record_id` points at it. Lineage: file -> batch -> record -> silver row.
- Instruments resolve through `e2_match.resolve` (approved identifiers only; trading: code, ISIN, name; administrator: administrator code, name; an FX row with no code takes the instrument of the same trade id from the other source). Portfolio by code. Unknown ones are held back (`held_back` source_record, listed in the result, `needs_approval`), the rest load.
- Signs: buy +qty / -cash, sell -qty / +cash, FX forward -sold / +bought (as `tools/seed_10uc.py`).
- Administrator "Amendment" rows supersede the latest row of that trade id (quantity, price, amount only), status `amended`.
- Per business date, set `trade_mode` on the landing record: `replace` (default) supersedes same trade ids and withdraws trades of a covered date (rows, daily file name date, stated period) that the file no longer lists, with a row of status `cancelled`; `append` keeps ids already there and adds new ones.
- One action: `trade_intake.load_folder(plane, folder, viewer, mode="replace")` lands and loads every CSV/XLSX in the folder.

Acceptance (clean Evergreen env, make_env, UC8 July folder)
- transactions: OMS 4 rows, administrator 4 rows, USD 1,408,050.00 each side (footer total).
- `trade_vs_admin` for 2026-07-31: checked 8 (4 + 4), 4 pairs matched, 0 breaks, nothing skipped.

For other lanes
- FIXB2 (recon): `_trades` does not skip status `cancelled`. A withdrawn trade would still be compared. It should drop `cancelled` rows.
- No API route or screen yet calls `load_folder`; the Upload page loads one file at a time and works for trade files through the hook.
- Identical-bytes files (the header-only no-trade days) are one landed file, so a re-sent empty day does not withdraw earlier trades for its date.
