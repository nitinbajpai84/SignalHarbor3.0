# UC8 answer key: do our trades agree with the administrator?

Synthetic data for the Evergreen Office demo. Entity Evergreen Family Trust (EG-TRUST), portfolio EG-LIQUID. Administrator: Northcott Fund Administration (synthetic). Counterparties: Synthetic Broker One (equities and bond), Harbour Bank (synthetic) (FX forwards). Rebuild with `python tools/make_uc8_data.py`. Files are in `docs/demo/uc8/sources/<YYYY-MM>/`.

Rules used for every figure:

- Compared = trades in the trading export for the month. Matched = same quantity, price and amount, and same date at the administrator.
- Net difference in USD = the amount the trade is out by. SGD differences are turned into USD at the month-end spot (30 Sep 2026: 1.3412).
- Allowance = 5,000 USD per break. "Over" means the net difference is above 5,000 USD; the excess is net minus 5,000.
- Break types: quantity, price (FX rate), missing (not booked at the administrator), timing (same numbers, different date; net 0).

## Arrival of the files

| Cycle | Trading export (daily CSV) | Administrator trade file (Excel) | Run date on the file |
|---|---|---|---|
| July 2026 | 1-31 Jul, one file per weekday | `2026-07/administrator_trade_confirmations_2026-07.xlsx` | 04 Aug 2026 |
| August 2026 | 3-31 Aug | `2026-08/administrator_trade_confirmations_2026-08.xlsx` | 02 Sep 2026 |
| September 2026 | 1-30 Sep | `2026-09/administrator_trade_confirmations_2026-09.xlsx` plus two OTC confirmation PDFs | 02 Oct 2026 |
| October 2026 | 1-30 Oct (31 Oct is a Saturday, no file) | `2026-10/administrator_trade_confirmations_2026-10.xlsx` plus one amended FX confirmation PDF | 03 Nov 2026 |

Business days are weekdays only (no holiday calendar, per the universe convention). Header-only CSVs are days with no trades.

## July 2026 (month-end 31 Jul): all match

| Trade | Date | Security | Side | Quantity | Price | Gross | Admin | Result |
|---|---|---|---|---|---|---|---|---|
| T-20260706-001 | 6 Jul | Meridian Foods | buy | 15,000 | 31.20 | 468,000.00 USD | same | matched |
| T-20260714-002 | 14 Jul | Bay Street Utilities | sell | 5,000 | 45.60 | 228,000.00 USD | same | matched |
| T-20260721-003 | 21 Jul | Coastal Rail 5.1% 2031 bond | buy | 500,000 | 0.9915 | 495,750.00 USD | same | matched |
| T-20260728-004 | 28 Jul | Coastal Rail Holdings | buy | 3,000 | 72.10 | 216,300.00 USD | same | matched |

**Expected:** compared 4, matched 4, breaks 0, net break 0.00 USD. Administrator footer total USD 1,408,050.00.

## August 2026 (month-end 31 Aug): one timing difference, clears

| Trade | Trade date (export) | Admin trade date | Security | Side | Quantity | Price | Gross | Result |
|---|---|---|---|---|---|---|---|---|
| T-20260804-001 | 4 Aug | 4 Aug | Meridian Foods | buy | 8,000 | 31.00 | 248,000.00 | matched |
| T-20260811-002 | 11 Aug | 11 Aug | Northwind Logistics | buy | 4,000 | 38.90 | 155,600.00 | matched |
| T-20260818-003 | 18 Aug | 18 Aug | Coastal Rail Holdings | buy | 2,000 | 73.40 | 146,800.00 | matched |
| T-20260827-004 | 27 Aug | **28 Aug** | Bay Street Utilities | sell | 8,000 | 46.83 | 374,640.00 | **timing** |

**Expected:** compared 4, matched 3, breaks 1 (timing, Bay Street Utilities T-20260827-004), net 0.00 USD. The item is within the allowance and is cleared: quantity, price and amount agree, only the booking date differs by one business day. Administrator footer total USD 925,040.00.

## September 2026 (month-end 30 Sep): three breaks

| Trade | Date | Security / issuer | Side | Export | Administrator | Break type | Net USD | Over 5,000 by |
|---|---|---|---|---|---|---|---|---|
| T-20260903-001 | 3 Sep | Meridian Foods | buy | 10,000 at 32.10 = 321,000.00 | same | matched | 0 | |
| T-20260910-002 | 10 Sep | Bay Street Utilities | sell | 6,000 at 47.30 = 283,800.00 | same | matched | 0 | |
| T-20260915-F01 | 15 Sep | FXF-2026-001 (USD 2,000,000 sell, SGD buy, Harbour Bank) | sell USD / buy SGD | SGD 2,680,000.00 at 1.3400 | same, 1.3400 | matched | 0 | |
| T-20260917-004 | 17 Sep | Northwind Logistics | buy | 12,000 at 42.15 = 505,800.00 | **10,200** = 429,930.00 | **quantity** | **75,870.00** | 70,870.00 |
| T-20260922-005 | 22 Sep | Coastal Rail Holdings | buy | 4,000 at 75.60 = 302,400.00 | same | matched | 0 | |
| T-20260929-F02 | 29 Sep | FXF-2026-002 (USD 3,000,000 sell, SGD buy, Harbour Bank) | sell USD / buy SGD | SGD 4,027,500.00 at **1.3425** | SGD 4,035,600.00 at **1.3452** | **price (rate)** | SGD 8,100 = **6,039.37** | 1,039.37 |
| T-20260929-007 | 29 Sep | Coastal Rail 5.1% 2031 bond | buy | 500,000 at 0.9913 = 495,650.00 | same | matched | 0 | |
| T-20260930-008 | 30 Sep | Harborview Semiconductor | **sell** | 5,000 at 118.40 = 592,000.00 | **no trade** | **missing** | **592,000.00** | 587,000.00 |

**Expected:** compared 8, matched 5, breaks 3, net break total 673,909.37 USD (all three over the allowance; excess total 658,909.37 USD). Administrator footer totals: USD 1,832,780.00 and SGD 6,715,600.00 (seven rows, Harborview not booked).

Sep OTC confirmations (`2026-09/otc_confirms/`): FXF-2026-001 dated 15 Sep, rate 1.3400, matches. FXF-2026-002 dated 29 Sep, buy SGD 4,035,600.00 at 1.3452, the source of the rate break.

## October 2026 (month-end 31 Oct): two September items cleared, one carried forward

October trades (all matched):

| Trade | Date | Security | Side | Quantity | Price | Gross | Result |
|---|---|---|---|---|---|---|---|
| T-20261001-009 | 1 Oct | Meridian Foods | buy | 20,000 | 33.10 | 662,000.00 | matched |
| T-20261002-010 | 2 Oct | Bay Street Utilities | sell | 10,000 | 48.20 | 482,000.00 | matched |
| T-20261007-011 | 7 Oct | Coastal Rail 5.1% 2031 bond | buy | 1,000,000 | 0.9910 | 991,000.00 | matched |

September items checked in the October file:

| Item from Sep | Administrator action in Oct | Status in Oct |
|---|---|---|
| T-20260917-004 Northwind Logistics quantity 10,200 | Amendment row, quantity corrected to 12,000 = 505,800.00, booked 6 Oct 2026 | **cleared** |
| T-20260929-F02 FXF-2026-002 rate 1.3452 | Amendment row, rate 1.3425 = SGD 4,027,500.00, booked 6 Oct 2026; amended confirmation PDF from Harbour Bank | **cleared** |
| T-20260930-008 Harborview Semiconductor sell 5,000 | No administrator row | **carried forward**, still 592,000.00 USD |

**Expected:** compared 3 new trades, matched 3, new breaks 0. Open at 31 Oct: one item, Harborview Semiconductor T-20260930-008, 592,000.00 USD, 587,000.00 over the allowance. Administrator footer totals USD 2,135,000.00 (three trades; amendment rows are not in the footer) and SGD 0.00.

## Planted issues and who acts

| # | Month | Issue | Expected product output | Who should act |
|---|---|---|---|---|
| U1 | Aug | Bay Street sell booked by the administrator one business day late (28 Aug) | Timing break, net 0, cleared, no case needed | Mei Chen (operations analyst) closes it; no action beyond noting it |
| U2 | Sep | Northwind Logistics quantity: export 12,000, administrator 10,200 (1,800 shares) | Quantity break, 75,870.00 USD, 70,870.00 over allowance | Mei Chen asks the administrator and the trading desk which quantity is right; Raj Patel (approver) signs off the correction |
| U3 | Sep | FX forward FXF-2026-002 rate: export 1.3425, confirmation 1.3452 (SGD 8,100) | Price break, 6,039.37 USD at 1.3412, 1,039.37 over allowance | Raj Patel (finance approver) decides the agreed rate and asks Harbour Bank for a corrected confirmation; Mei Chen tracks it |
| U4 | Sep | Harborview Semiconductor sell 5,000 at 118.40 (592,000.00) with no administrator trade | Missing break, 592,000.00 USD, 587,000.00 over allowance | Mei Chen chases the administrator; Sofia Reyes (risk owner) is told because it is the largest item; Daniel Foo (sponsor) sees it on the Today list |
| U5 | Oct | Northwind and FX items corrected by the administrator (6 Oct) | Both cleared in October, both with the amendment reference | Mei Chen closes them with Raj Patel's sign-off on the FX rate |
| U6 | Oct | Harborview still missing at the administrator | Carried forward, 592,000.00 USD still open | Mei Chen keeps chasing; Sofia Reyes reviews the open item |

Clean cycles (July, and the October new trades) are there so the product can show matches as well as breaks.

## Conflicts with the seeded 10-use-case universe (for Nitin to decide)

These files follow the UC8 story as written for this run (Aug timing, Sep three breaks, Oct two cleared and one carried). The seeded universe in `docs/test/10uc_universe.json` and `tools/seed_10uc.py` is different:

1. The universe books the Northwind quantity break, the Harborview missing sell and the FX rate break on **2, 6 and 5 Oct 2026**, not in September. Trade ids in the universe for these items are T-20261002-003, T-20261006-005 and T-20261005-004 (FXF-2026-002 trade date 5 Oct, value 5 Jan 2027). Here they are dated in September, with ids T-20260917-004, T-20260930-008 and T-20260929-F02 (FXF-2026-002 trade date 29 Sep, same value date 5 Jan 2027).
2. The universe's October matched trades have other ids (T-20261001-001, T-20261002-002, T-20261007-006). Here they are T-20261001-009, T-20261002-010, T-20261007-011, so the two sets never collide in one product database.
3. The universe run for 9 Oct gives 13 compared and 3 breaks over 30 days. These four monthly files give a different count per cycle. Loading both sets into one database would double-count the same instruments.
4. The universe rates FXF-2026-002 at 8 Oct MTM and uses spot 1.3388 for the USD figure. Here 1.3412 (30 Sep spot) is used, so the USD figure is 6,039.37, not 6,050.19.

If the demo must keep the universe's October dates, the Sep story needs to move to October or the universe changes. This should be a decision before the seed is rebuilt.
