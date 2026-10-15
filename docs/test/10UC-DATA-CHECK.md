# 10UC fixtures: data check (synthetic)

Reviewed 2026-10-09 against `docs/test/10uc_universe.json` (as of 2026-10-09, cutoff 18:00 UTC). Every category under `tests/v1/fixtures/10uc/` was opened and every figure compared with the universe by `tools/gen_10uc/check_10uc.py` (read-only; re-run it after any generator change, exit code 1 on a failure). 2,626 checks, 0 failing after the fixes below. All 16 generators in `tools/gen_10uc/` run clean from the universe alone, with no randomness.

Scope of the check, per category: figures equal the universe; cross-file consistency (administrator positions vs security master vs month-end prices; notices vs commitments register; trading export vs OTC confirmations; bank cash vs administrator cash; issued report packs vs the valuations known at their cutoff); every planted fact present once where it belongs; no real-world firm, index or person name (sweep of 90 real names over all 180 files, including PDF and xlsx text).

## Summary

| Category | Files | Result | Issues fixed | Issues open |
|---|---|---|---|---|
| admin_exports | 12 xlsx + manifest | pass (1,271 checks) | Valuation Date on a carried value now shows the period end of the statement the value came from (Fund D 2026-03-31, Fund C 2026-06-30 in the Sep file), so the 192 / 101 day ages of P07 and P18 can be read from the file. Was the month end on every line. Manifest updated. | The renamed column (`Valuation Amount (USD)` in 2026-03) is a generator choice; the universe has no such fact. Oct 2025 EG-GROWTH NAV 0.00 and EG-FUNDS 10,444,500 come from "Not received" rows in the universe (investment view 13.6M / 22.4M); deliberate but visible. Funds are exported as quantity 1 x price = value, since they have no units in the universe (L1/L2 units exist but are not used here). |
| security_master | 1 xlsx + manifest | pass (449) | none | ISINs are synthetic codes not held by the universe (ZZ prefix). |
| bank_cash | 3 xlsx + manifest | pass (188) | none | The universe does not say which view the bank agrees with; the generator takes the administrator everywhere except Entity B on 8 Oct, where the bank shows the trading export's 868,000 (P08 break of 12,400). Weekend rows are present because `cash_daily` holds them. Bank names and account numbers are placeholders. |
| trading_export | 22 csv + manifest | pass (44) | none | `FXF-2026-001` has no row in `trades_oct`; its export row (`T-20260915-F01`) is derived from `fx_forwards`. P06 says "no trades in September" while that forward traded 15 Sep (wording only: it is not a security trade). |
| otc_confirms | 2 pdf + manifest | pass (8) | none | none |
| issued_reports | 3 xlsx + 3 pdf + manifest | pass (42) | none | Only the September pack is fixed by the universe. July and August follow the same cutoff pattern; July's A and B lines are the June values (the July statements arrived 5 Aug, after the 4 Aug cutoff) and carry the status word "carried", which is not a universe word. |
| manager_statements | 63 pdf + manifest | pass (324) | none | 24 L1/L2 statements have no PDF (scoped out). "Final - Amended" is the generator's label for `kind = amended`. The Fund C amended row has due 2026-07-14, received 2026-08-18, but `late_business_days` 0 in the universe. |
| notices | 17 pdf + manifest | pass (82) | none | none; cumulative called equals `called_to_date` for every fund after the last call noticed by 30 Sep. |
| commitments | 1 xlsx + manifest | pass (30) | none | none |
| emails | 19 eml + manifest | pass (59) | Addresses now the universe's own (`people[].email`, `managers[].contact_email`); the generator had invented `*@evergreen.example.test` and `*.example.test` variants. The Fund C amended email now says the replaced final was issued 9 July 2026 (`received_at` 2026-07-09T10:00Z) instead of "10 July", which came from the universe note text. | Message-IDs stay on `example.test`. |
| market_data | 2 csv + manifest | pass (75) | none | none |
| benchmark_workbook | 1 xlsx + manifest | pass (11) | none | EG-LIQUID 4.1667% and the 1.9065 point gap are not in the workbook (portfolio figures). |
| policy | 1 pdf + manifest | pass (11) | none | Rule parameters (5,000 USD, 100,000 USD / 0.5%, 10 business days, WMR 4pm, 30 days, the four limit ranges) match; the limit rules are laid out as a table and the cash rule is paraphrased, so the `definition_text` strings are not verbatim. Strategic targets are stated as not set (the universe has none). |
| process_narrative | 1 md + 1 txt + manifest | pass (10) | none | none |
| research_docs | 4 pdf + manifest | pass (4) | none | Key facts carry the universe's figures and names but are re-phrased (for example "USD 2.4 bn (synthetic)"). |
| notes | 8 md + manifest | pass (9) | Added `07_investment_committee_note_2026-09-17.md` for `doc-ic-01` (title, date and both key facts from the universe; the HVS figure is the 31 Aug liquid book value). The folder had only an October note, which is not a universe document; it is kept as `08_...2026-10-08.md`. | doc-note key facts are paraphrased in places (figures present). |

Cross-category checks that passed: every administrator code and instrument name in the 12 exports exists in the security master under the same name; every alias in the master maps to one id, and every universe name variant, ticker and code is in the alias map (P13); liquid book lines equal the month-end prices and totals in all 12 months; approved NAV equals the sum of positions in all 48 portfolio-months; the three bank files equal administrator cash on 89 of 90 entity-days (P08 the one break); the seven export rows equal `trades_oct` / `fx_forwards`, FXF-2026-001 agrees with its confirmation and FXF-2026-002 differs by exactly SGD 8,100.00 (P30); the 17 notices agree with the commitments register and the Notices sheet; the three issued packs equal the statements known at each cutoff and the Sep pack carries no trace of 10,180,000 (P02 baseline).

Planted facts present exactly once where planned: P01, P02, P03-P05 (NAVs), P07, P08, P10, P11 (one unsent draft, no D June file), P12 (three amended PDFs, one each), P13, P14, P15, P16, P17, P18, P19, P21-P24, P25, P28, P29, P30, P31, P32, P33.

## Open points for the data architect (not fixed here)

1. Universe note on the Fund C amended statement says "final of 10 Jul 2026"; the final's `received_at` is 2026-07-09. Fixtures follow the date field.
2. Universe note on the Fund A amended statement names `tools/make_e2_statements.py`; `tools/gen_10uc/manager_statements.py` now produces that PDF.
3. P06 wording "no trades in September" vs the 15 Sep FX forward.
4. The xlsx files are content-deterministic (every zip entry byte-identical on re-run) but the zip container timestamps change, so a whole-file hash moves on each run. PDFs, csv, eml, md and txt hash identically.
5. No generator or fixture names a real company, index or person; indices are "Global Equity Index (synthetic)" and "Global Bond Index (synthetic)".
