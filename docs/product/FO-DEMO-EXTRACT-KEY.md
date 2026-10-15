# Answer key: extraction test documents (card D5)

Outside the product. 18 synthetic documents numbered 25 to 42, added to the 24 of `FO-DEMO-DOCS-KEY.md`, in `data/<company>/documents/` (copy in `local/documents/<company>/`). Plain Markdown or text. Base currency SGD. Structured values come from `data/<company>/landing/` (month-end `custodian_positions` files) and agree with `FO-DEMO-ANSWER-KEY.md`.

## Families and layouts

| Family | Layout 1 | Layout 2 |
|---|---|---|
| Custodian statement | A: labelled lines per account ("Securities market value (SGD)"): files 25, 26 | B: tables, "Acct Ref", "Securities value (SGD)", "Grand total", cash in a second table: file 27 |
| Capital call | Wording 1: table with commitment, called before, this call, called after, remaining unfunded, bold due date: files 29, 30, 42 | Wording 2: prose drawdown request, "paid-in capital", "undrawn commitment", amount drawn in a sentence: files 31, 32 |
| Fee invoice | Design 1: table of lines with a bold Total: files 33, 34 (management fee); 09 to 11 already exist | Design 2: plain heading plus indented lines ending "Amount payable": files 35 (custody), 36 (performance fee) |

Extra layouts: 28 table-heavy fixed-width holdings export with page subtotals; 37 scan-like OCR text; 38, 39 emails with figures in words; 40 capital account with different labels; 41 distribution advice in prose.

Files: 25 statement A 2026-08-31; 26 statement A 2026-09-30; 27 statement B 2026-07-31; 28 holdings table NC-001 2026-08-31; 29 call Sentosa III; 30 call Changi IV; 31 call Orchard I (wording 2); 32 call Marina II (wording 2); 33 invoice Orchard I H1; 34 invoice Changi IV H1; 35 custody invoice Q3 (design 2); 36 performance fee Sentosa III (design 2); 37 OCR custody invoice Q1; 38 email Orchard Q3 estimate; 39 email Northgate August fees; 40 capital account Sentosa III; 41 distribution Orchard I (wording 2); 42 corrected call Marina II.

## Values to extract

### Custodian statements (fields: statement date, per account securities market value, total, cash by currency)
- 25, layout A, 31 Aug 2026: NC-001 56,022,858.47; NC-002 91,403,073.69; NC-003 31,786,406.25; total 179,212,338.41. Cash: NC-001 SGD 937,525.21, USD 309,124.77; NC-002 EUR 777,404.10, SGD 637,150.35, USD 1,406,875.90; NC-003 HKD 7,887,714.79, SGD 1,600,176.22, USD 726,834.15.
- 27, layout B, 31 Jul 2026: NC-001 56,441,212.12 (11 lines); NC-002 89,098,942.42 (20); NC-003 31,145,428.53 (10); grand total 176,685,583.07 (41 lines). Cash in original currency as in `custodian_cash_2026-07.csv`.
- 26, layout A, 30 Sep 2026: NC-001 56,398,593.20; **NC-002 93,507,383.18**; NC-003 32,677,358.82; total 182,583,335.20.

### Capital calls (fields: fund, call number, amount, currency, due date, commitment, called before, called after, unfunded after, reference, notice date)
- 29: Sentosa Growth Partners III, call 3, USD 700,000, due 21 Sep 2026, commitment 8,000,000, before 5,600,000, after 6,300,000, unfunded 1,700,000, ref SGP3-C3-2026, notice 1 Sep 2026.
- 30: Changi Growth Partners IV, call 2, SGD 500,000, due 30 Sep 2026, commitment 6,000,000, before 3,600,000, after 4,100,000, unfunded 1,900,000, ref CGP4-C2-2026, notice 10 Sep 2026.
- 31 (wording 2): Orchard Growth Partners I, USD 800,000, required by 12 Oct 2026, commitment 10,000,000, paid in before 7,700,000, after 8,500,000, undrawn 1,500,000, ref OGP1-C6-2026, notice 21 Sep 2026. The call number (6) is not written; it follows call 5 (USD 1,200,000, document 04). Email 38 repeats the figures.
- 32 (wording 2): Marina Growth Partners II, call 5 (number only in the reference MGP2-C5-2026), SGD 900,000, commitment 12,000,000, paid in before 9,000,000, after 9,900,000, undrawn 2,100,000, notice 15 Sep 2026. **Due date missing.**
- 42 (wording 1): corrected notice for the same call: call 5, SGD 900,000, due 30 Oct 2026, notice 22 Sep 2026, same reference; supersedes 32. It names Harbour Bank HB-USD-01 for an SGD call (a point for a human, not a planted field error).

### Fee invoices (fields: invoice number, date, period, lines, total, currency)
- 33: OCM-2026-H1-044, 6 Jul 2026, 1 Jan to 30 Jun 2026, management fee USD 75,000 (1.5 % of 10,000,000, half a year), expenses USD 6,200, total USD 81,200.
- 34: CPL-2026-0391, 8 Jul 2026, same period, management fee SGD 60,000 (2.0 % of 6,000,000, half a year), expenses SGD 4,150, total SGD 64,150.
- 35 (design 2): NC-2026-0931, issued 6 Oct 2026, 1 Jul to 30 Sep 2026; safekeeping SGD 26,925 (0.06 % x 179,500,000 / 4, the rounded mean of the three month-end totals); 138 trades x 25 = 3,450; 2 events x 150 = 300; amount payable SGD 30,675. Ties to the fee agreement (document 23) and clears the SGD 15,000 minimum.
- 36 (design 2): SCM-PF-2026-007, 14 Aug 2026, carry USD 50,000 (20 % of USD 250,000, the gain in document 06); SGD 68,000 at 1.36. No period field, only "Financial year".

## Planted traps

| No | File | Trap | Expected behaviour |
|---|---|---|---|
| T1 | 26 | NC-002 stated as 93,507,383.18; structured positions of 30 Sep sum to 93,570,383.18 (digits transposed, difference 63,000.00). The statement total is consistent with its own lines (182,583,335.20) but not with the structured total 182,646,335.20. | `ties_to` fails; document goes to review; no guess |
| T2 | 25, 27 | Totals agree with the sum of `market_value_base` per account and date to the cent. | `ties_to` passes |
| T3 | 28 | Holdings of NC-001 at 31 Aug 2026 (11 lines over 2 pages: 6 and 5); account total 56,022,858.47 equals statement 25 and the structured file. Subtotals and running totals repeat per page. | Take only the account total line, not page subtotals; `ties_to` passes |
| T4 | 32 | Required field `due_date` absent. | Missing required field, review queue |
| T5 | 32, 42 | Corrected notice for the same reference. | Later notice supersedes; the two must not be summed |
| T6 | 37 | OCR: O for 0, l for 1 (also "3l March"), "nurnber", a broken line ("quar-" / "ter"); total prints as `2535000` for SGD 25,350.00 (comma and decimal point lost). Real values: invoice NC-2026-0318, 6 Apr 2026, 1 Jan to 31 Mar 2026; custody fee 21,600 (0.06 % x 144,000,000 / 4); 132 trades x 25 = 3,300 (printed 3,3O0); 3 events x 150 = 450; total 25,350. | Lines add up to 25,350, so a "total = sum of lines" check catches the missing decimal and proposes 25,350.00 for confirmation; never accepts 2,535,000 |
| T7 | 38 | Figures in words: NAV about USD 12.1 million (+2.2 % on the quarter), family share "a little over" USD 1.7 million (14.2 % x 12.1 million = 1.718), drawdown USD 800,000 due 12 Oct, undrawn USD 1.5 million. Estimates, unaudited. | Extract with an estimate flag; ties to 31 (800,000; 1,500,000) |
| T8 | 39 | Figures in words: custody accrual about SGD 9,800, 47 trades (SGD 1,175 = 47 x 25), 1 event (SGD 150). Also announces layout B (file 27). | Accrual is approximate; trade fee exact |
| T9 | 40 | Same fields, other names: "Total pledged" = commitment 8,000,000; "Paid-in capital" = called to date 5,600,000; "Undrawn commitment" = unfunded 2,400,000; "Capital returned" = distributed 600,000; "Fair value of interest" = NAV 6,120,000; "Valuation as at" = NAV date 30 Jun 2026. | Map to the same fields via the glossary note; paid-in plus undrawn equals pledged |
| T10 | 41 | Distribution in prose: USD 300,000 paid 15 Sep 2026 = 200,000 capital + 100,000 gain. | Parts sum to the total |
| T11 | 36 | Two currencies on the page (USD 50,000 payable, SGD 68,000 for the books). | Take the amount labelled "Amount payable (USD)" |
| T12 | 31 | Call number absent from the text. | Derive from the reference or flag (optional field) |

## Checks the files support
- `present`: 32 lacks the due date.
- `parses`: 37 total; 38 and 39 amounts in words.
- `range`: unfunded after never above commitment (29, 30, 31, 32, 42).
- `ties_to`: statements 25 and 27 pass, 26 fails, 28 passes; capital calls: before + this = after; invoice lines sum to total (33, 34, 35, 37).
