# D · Data that makes sense for all ten use cases — landed

Files (all new, nothing existing edited, so no backups were needed): `tools/seed_10uc.py`, `docs/test/10UC-ANSWER-KEY.md`, `tests/v1/test_seed_10uc.py`.

## What it does
`python tools/seed_10uc.py --data-root <empty folder>` runs `seed_evergreen` (company, people, 30 Sep story), then adds 13 months of coherent history from `docs/test/10uc_universe.json`, then runs `seed_v3_demo` (project, gold tables, dashboard) so the gold tables see everything. About 25 seconds; a second run changes nothing. `--hold-amended-a` leaves Fund A's 7 Oct amended statement out so a demo can drop the PDF in. `--reset` rebuilds the Evergreen warehouse (it refuses a root that already holds the old one-month demo rows unless `--reset` is given).

History to 3 Oct is back-dated with explicit `recorded_at` (statements and notices registered as documents, values linked to document, page and line). What arrives after the 3 Oct report goes through the product's writers: `e2_extract.confirm` (Fund A amended, the October notices), `k6_liquidity.record_commitment` and `record_notice`, `e1_write.record_many` (trades), `e3_recon.run_detail` (cash, trades, limits), `k7_benchmark.certified_return` (the in-progress benchmark question). Fund E's Q3 statement is read and left unconfirmed.

## Tests
`SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_seed_10uc.py -q` : 28 passed (about 70 s; it seeds two temporary roots). Each planted fact P01 to P33 is asserted from the product's own functions; the answer key names every one.

## Wiring for the orchestrator
The product differs from the universe in these places; the key follows the product. None is a file of this card.
1. `sh_platform/v1/e3_recon.py` `_limits` applies every limit rule to every portfolio and ignores `portfolio_code`. The seed therefore signs ceilings only and names the holding in the single-name cap. Honour `portfolio_code`, then restore the universe's floors (listed equity 60, hedge funds 20) and decide whether the single-name cap is "any holding" (that breaches on six names at 5%).
2. `sh_platform/v1/e3_rules.py` `RULE_TYPES` still lacks `limit`, so a limit cannot be proposed in Settings; the seed writes the signed limit rules directly, as the base seed writes its rules.
3. `sh_platform/v1/k6_liquidity.py` `forecast`: no "paid" state, so every past confirmed call sits in Overdue (Entity B 12,100,000; Evergreen Holdings 18,450,000). Add a paid state (still counted as called) or limit Overdue to unpaid calls.
4. `sh_platform/v1/e2_extract.py`: the rule-based reader cannot pair a label with a value on the next line (the fixture PDFs from the universe generator are laid out that way), and `e2_intake.register` cannot match the fund from the heading of those PDFs. Either extend `_locate`/`fund_names` or change the generators to "Label: value" lines. Also `_record_valuation` records `portfolio_id` NULL for the first value on a new valuation date (Fund E's Q3 statement), which hides it from every portfolio; the seed writes that row with its portfolio.
5. `sh_platform/v1/e3_calc.py` `portfolio_value` counts trading-export cash as a holding. The Office view lists a "Cash ... unverified" line per portfolio and the NAV bridge at today's date shows cash as timing. The seed loads trading-export cash only from 1 Oct and the key reads the bridge for 30 Sep. Consider excluding cash instruments from `portfolio_value`, or defaulting the bridge date to the NAV date.
6. `tools/seed_evergreen.py` writes Fund B's 30 Sep value with `approval_status = 'official'`; the product reads `approved` (anything else shows Unverified). `seed_10uc` corrects that one row; fix the base seed and the correction becomes a no-op.
7. `tools/seed_v3_demo.py` `HOLDINGS_SQL` builds one month and counts the liquid roll-up position as a second holding; its cash tile has no day filter. `seed_10uc` hands its own carried-forward SQL to that module before it builds and narrows the cash tile to the latest day. Move both into `seed_v3_demo.py` and drop the override.
8. `e1_asof.SUPERSEDES` still lacks `commitments` (K4 note); `tests/v1/test_e0a.py` and `test_d1.py` still count 41 core tables (K4 note).
9. `python-docx` is not installed, so "Download the SOP" gives Markdown here.
10. Not seeded: the July and August issued reports (`e1_reports.issue(..., issued_at=...)` could write them), FX forward marks (they are not in the 41,200,000), and the daily index-level file (month-end levels are enough for every figure). Loading the fixture xlsx/csv through E0c would stamp every row "now", so the administrator exports, bank files and trading CSVs are represented by the same figures written back-dated.
11. Dates: `k6_liquidity.alert_if_due` uses today's date, so a run after 4 Nov 2026 also opens a Finance case for Fund D's 4 Dec call (the tests do not count capital-call cases). K3's inbox defaults to today; the tests pass the date.

## Wiring for the orchestrator (fix round, 9 Oct)
12. Must before the demo: the Office view NAV bridge at its default date (today) shows Evergreen Growth 18,880,000 against 16,400,000 and Entity B 23,743,000 against 22,525,000 because trading-export cash of 8 Oct is counted as a holding (the Holdings total is 107,721,200 against the dashboard's 103,405,000). Exclude cash instruments from `portfolio_value`, or default the bridge date to the NAV date.
13. The approver and participant roles get 403 on `/api/v1/library` and `/api/v1/pulse2/items` (c4 permissions), and `/api/v1/cases` (e4 listing) hides the policy-question case from Raj and Sofia. Widen the permissions/listing or accept it; the key now says so.
14. K6: the stale-data limit case title lower-cases the manager ("Limit breached · cedarpoint ventures · ..."); fix the title in `e3_recon`.
15. Demo window is 9-14 Oct 2026 (today-dated inbox, stale-data limit and alert); either pass the seed's as_of to those pages or reseed.
