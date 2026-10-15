# Evergreen Office: the ten use case universe (synthetic)

As of 2026-10-09, cutoff 2026-10-09T18:00:00Z. Machine file: `docs/test/10uc_universe.json`, written by `docs/test/make_10uc_universe.py` (fixed seeds). Every fixture, seed and expected figure must come from the JSON. All names, managers, funds, people and indices are fictional; money in USD unless stated.

## Conventions

- Business days are weekdays; no holiday calendar.
- A statement is due 10 business days after its period end (statement_due); late = business days after the due date.
- The administrator NAV of a portfolio is the sum of its investment holdings at the values the administrator had at 06:00 UTC on the 2nd business day after the month end; cash is held at entity level and reported in the cash file, not inside the portfolio NAV (this keeps the seed's EG-GROWTH NAV of 16,400,000 = A 10,000,000 + B 6,400,000).
- Known now = the latest statement for the period received by the cutoff, whatever its status; the Fund A amended statement counts as known only once the demo drops it.
- Quarterly funds carry their last statement forward in the months between; any value older than 90 days at the as-of date is Stale (C and D at 9 Oct 2026).
- The liquid book instrument 'Evergreen Liquid Book' is the sum of the 20 securities; quantity x price = value on every line.
- Bond prices are per 1.00 nominal (4 dp); the convertible is quoted per unit; equities per share.
- FX forward mark-to-market = buy_amount / spot - sell_amount (forward points ignored).
- Index and FX daily levels: linear interpolation between month-end anchors over business days, 2 dp (indices) or 4 dp (FX); no noise.

## People

| Name | Role in the office | Platform role |
|---|---|---|
| Daniel Foo | Chief Investment Officer | sponsor |
| Mei Chen | Operations analyst | analyst |
| Raj Patel | Finance | approver |
| Sofia Reyes | Risk | participant |
| Anita Rao | Head of data | analyst |
| Leo Park | Data engineer | analyst |
| Grace Ong | Company admin | company_admin |

## Entities and portfolios

| Portfolio | Entity | Name | Holdings |
|---|---|---|---|
| EG-GROWTH | EG-HOLD | Evergreen Growth portfolio | A, B |
| EG-LIQUID | EG-TRUST | Evergreen Liquid portfolio | LIQ |
| EG-B-OPS | EG-B | Entity B operating portfolio | C, D, E |
| EG-FUNDS | EG-TRUST | Evergreen Funds portfolio | H1, H2, L1, L2 |

## Managers and funds

| Key | Fund | Type | Asset class | Manager | Frequency | Admin code | Portfolio | Names seen on statements |
|---|---|---|---|---|---|---|---|---|
| A | Evergreen Growth I | private_fund | private_equity | MGR-NORTHGATE | monthly | 4471 | EG-GROWTH | EG Growth Fund I; Fund A - Evergreen Growth I; Evergreen Growth I |
| B | Evergreen Income II | private_fund | private_credit | MGR-BLUEWATER | monthly | 4472 | EG-GROWTH | Fund B - Evergreen Liquid Book; Fund B - Evergreen Income II; Evergreen Income II |
| C | Cedarpoint Ventures III | private_fund | venture | MGR-CEDARPOINT | quarterly | 4473 | EG-B-OPS | Cedarpoint Ventures III, L.P.; CPV III |
| D | Cedarpoint Opportunities II | private_fund | private_equity | MGR-CEDARPOINT | quarterly | 4474 | EG-B-OPS | Cedarpoint Opportunities Fund II; CPO II |
| E | Saltmarsh Infrastructure Fund II | private_fund | infrastructure | MGR-SALTMARSH | quarterly | 4475 | EG-B-OPS | Saltmarsh Infra II; SIF II |
| H1 | Kestrel Ridge Macro Fund | hedge_fund | hedge_fund | MGR-KESTREL | monthly | 4481 | EG-FUNDS | Kestrel Ridge Macro Fund; KR Macro Fund Ltd - Class B USD |
| H2 | Kestrel Ridge Equity Long/Short Fund | hedge_fund | hedge_fund | MGR-KESTREL | monthly | 4482 | EG-FUNDS | Kestrel Ridge Equity L/S; KR Equity Long Short Ltd |
| L1 | Global Equity Index Fund (synthetic) | liquid_fund | listed_equity | MGR-MERIDIAN | monthly | 4491 | EG-FUNDS | Meridian Global Equity Index Fund |
| L2 | Global Bond Index Fund (synthetic) | liquid_fund | bond | MGR-MERIDIAN | monthly | 4492 | EG-FUNDS | Meridian Global Bond Index Fund |
| LIQ | Evergreen Liquid Book | liquid_book | listed |  | daily |  | EG-LIQUID |  |

## Liquid book at 30 Sep 2026 (EG-LIQUID, total 41,200,000.00)

| Key | Security | Asset class | Quantity | Price | Value |
|---|---|---|---|---|---|
| HVS | Harborview Semiconductor | listed_equity | 20000 | 118.40 | 2368000.00 |
| NWL | Northwind Logistics | listed_equity | 50000 | 41.90 | 2095000.00 |
| BSU | Bay Street Utilities | listed_equity | 40000 | 48.05 | 1922000.00 |
| MRF | Meridian Foods | listed_equity | 60000 | 32.80 | 1968000.00 |
| CRH | Coastal Rail Holdings | listed_equity | 30000 | 77.50 | 2325000.00 |
| LKH | Larkspur Health | listed_equity | 40000 | 56.25 | 2250000.00 |
| TWE | Tidewater Energy | listed_equity | 70000 | 29.40 | 2058000.00 |
| GBM | Granite Bay Materials | listed_equity | 50000 | 38.60 | 1930000.00 |
| OLR | Orchard Lane Retail | listed_equity | 80000 | 24.75 | 1980000.00 |
| SPS | Silverpine Software | listed_equity | 20000 | 102.30 | 2046000.00 |
| BHI | Blue Heron Insurance | listed_equity | 30000 | 64.10 | 1923000.00 |
| KFT | Kingfisher Telecom | listed_equity | 90000 | 21.60 | 1944000.00 |
| RWP | Redwood Pharma | listed_equity | 40000 | 47.35 | 1894000.00 |
| AHS | Atlas Harbour Shipping | listed_equity | 60000 | 35.20 | 2112000.00 |
| JCB | Juniper Consumer Brands | listed_equity | 50000 | 44.30 | 2215000.00 |
| EBG | Evermore Banking Group | listed_equity | 70000 | 31.15 | 2180500.00 |
| CRB31 | Coastal Rail 5.1% 2031 bond | bond | 2000000 | 0.9910 | 1982000.00 |
| HTN29 | Harbour Treasury Note 2029 (synthetic sovereign) | bond | 3000000 | 0.9725 | 2917500.00 |
| KFB30 | Kingfisher Telecom 4.6% 2030 bond | bond | 2000000 | 0.9840 | 1968000.00 |
| PRC29 | Pacific Rim Convertible 2029 note | (none) | 10000 | 112.20 | 1122000.00 |

Month-end totals: 2025-10-31 40216100.00, 2025-11-30 40112500.00, 2025-12-31 39970900.00, 2026-01-31 40173000.00, 2026-02-28 39953600.00, 2026-03-31 39717300.00, 2026-04-30 39598100.00, 2026-05-31 39685700.00, 2026-06-30 39806800.00, 2026-07-31 39819400.00, 2026-08-31 39552000.00, 2026-09-30 41200000.00

## FX forwards (OTC, EG-LIQUID)

| Id | Trade | Value date | Sell USD | Buy SGD | Rate | Confirmation rate | Status |
|---|---|---|---|---|---|---|---|
| FXF-2026-001 | 2026-09-15 | 2026-12-15 | 2000000.00 | 2680000.00 | 1.3400 | 1.3400 | matched |
| FXF-2026-002 | 2026-10-05 | 2027-01-05 | 3000000.00 | 4027500.00 | 1.3425 | 1.3452 | mismatch |

## Statements (every one, Oct 2025 to Sep 2026)

| Fund | Period end | Kind | Value | Received | Due | Late (bd) | Status | Note |
|---|---|---|---|---|---|---|---|---|
| A | 2025-10-31 | final | 8062905.00 | 2025-11-06 | 2025-11-14 | 0 | official |  |
| A | 2025-11-30 | final | 8361232.00 | 2025-12-05 | 2025-12-12 | 0 | official |  |
| A | 2025-12-31 | final | 8608724.00 | 2026-01-06 | 2026-01-14 | 0 | official |  |
| A | 2026-01-31 | final | 8480454.00 | 2026-02-04 | 2026-02-13 | 0 | official |  |
| A | 2026-02-28 | final | 8816280.00 | 2026-03-03 | 2026-03-13 | 0 | official |  |
| A | 2026-03-31 | final | 8868296.00 | 2026-04-02 | 2026-04-14 | 0 | official |  |
| A | 2026-04-30 | final | 9087343.00 | 2026-05-05 | 2026-05-14 | 0 | official |  |
| A | 2026-05-31 | final | 8976477.00 | 2026-06-03 | 2026-06-12 | 0 | official |  |
| A | 2026-06-30 | final | 9265520.00 | 2026-07-03 | 2026-07-14 | 0 | official |  |
| A | 2026-07-31 | final | 9442491.00 | 2026-08-05 | 2026-08-14 | 0 | official |  |
| A | 2026-08-31 | final | 9400000.00 | 2026-09-02 | 2026-09-14 | 0 | official |  |
| A | 2026-09-30 | estimate | 10000000.00 | 2026-10-02 | 2026-10-14 | 0 | estimated |  |
| A | 2026-09-30 | amended | 10180000.00 | 2026-10-07 | 2026-10-14 | 0 | official | Not loaded by the seed; the demo drops the PDF (tools/make_e2_statements.py). Known now after loading: 10,180,000. |
| B | 2025-10-31 | final | 5572795.00 | 2025-11-07 | 2025-11-14 | 0 | official |  |
| B | 2025-11-30 | final | 5546046.00 | 2025-12-04 | 2025-12-12 | 0 | official |  |
| B | 2025-12-31 | final | 5502787.00 | 2026-01-06 | 2026-01-14 | 0 | official |  |
| B | 2026-01-31 | final | 5569921.00 | 2026-02-06 | 2026-02-13 | 0 | official |  |
| B | 2026-02-28 | final | 5605568.00 | 2026-03-04 | 2026-03-13 | 0 | official |  |
| B | 2026-03-31 | final | 5726088.00 | 2026-04-06 | 2026-04-14 | 0 | official |  |
| B | 2026-04-30 | final | 5730669.00 | 2026-05-04 | 2026-05-14 | 0 | official |  |
| B | 2026-05-31 | final | 5835540.00 | 2026-06-05 | 2026-06-12 | 0 | official |  |
| B | 2026-06-30 | final | 5953418.00 | 2026-07-07 | 2026-07-14 | 0 | official |  |
| B | 2026-07-31 | final | 6008189.00 | 2026-08-05 | 2026-08-14 | 0 | official |  |
| B | 2026-08-31 | final | 6016000.00 | 2026-09-02 | 2026-09-14 | 0 | official |  |
| B | 2026-09-30 | final | 6400000.00 | 2026-10-01 | 2026-10-14 | 0 | official |  |
| C | 2025-09-30 | final | 7700000.00 | 2025-10-09 | 2025-10-14 | 0 | official |  |
| C | 2025-12-31 | final | 7900000.00 | 2026-01-09 | 2026-01-14 | 0 | official |  |
| C | 2026-03-31 | final | 8150000.00 | 2026-04-09 | 2026-04-14 | 0 | official |  |
| C | 2026-06-30 | final | 8420000.00 | 2026-07-09 | 2026-07-14 | 0 | official |  |
| C | 2026-06-30 | amended | 8275000.00 | 2026-08-18 | 2026-07-14 | 0 | official | Replaces the 8,420,000 final of 10 Jul 2026; a portfolio company write-down of 145,000. |
| D | 2025-09-30 | final | 4300000.00 | 2025-10-09 | 2025-10-14 | 0 | official |  |
| D | 2025-12-31 | final | 4400000.00 | 2026-01-09 | 2026-01-14 | 0 | official |  |
| D | 2026-03-31 | final | 4650000.00 | 2026-04-21 | 2026-04-14 | 5 | official |  |
| D | 2026-06-30 | missing |  |  | 2026-07-14 |  | missing | Never received. Due 14 Jul 2026. |
| E | 2025-09-30 | final | 8700000.00 | 2025-10-09 | 2025-10-14 | 0 | official |  |
| E | 2025-12-31 | final | 8900000.00 | 2026-01-09 | 2026-01-14 | 0 | official |  |
| E | 2026-03-31 | final | 9250000.00 | 2026-04-09 | 2026-04-14 | 0 | official |  |
| E | 2026-06-30 | final | 9600000.00 | 2026-07-24 | 2026-07-14 | 8 | official |  |
| E | 2026-09-30 | final | 9950000.00 | 2026-10-08 | 2026-10-14 | 0 | unverified | Extracted by Span on 8 Oct; Mei Chen has not confirmed the extraction yet. |
| H1 | 2025-10-31 | final | 6953044.00 | 2025-11-07 | 2025-11-14 | 0 | official |  |
| H1 | 2025-11-30 | final | 7075418.00 | 2025-12-05 | 2025-12-12 | 0 | official |  |
| H1 | 2025-12-31 | final | 7130606.00 | 2026-01-07 | 2026-01-14 | 0 | official |  |
| H1 | 2026-01-31 | final | 7135597.00 | 2026-02-06 | 2026-02-13 | 0 | official |  |
| H1 | 2026-02-28 | final | 7000734.00 | 2026-03-06 | 2026-03-13 | 0 | official |  |
| H1 | 2026-03-31 | final | 7037138.00 | 2026-04-07 | 2026-04-14 | 0 | official |  |
| H1 | 2026-04-30 | final | 7040657.00 | 2026-05-07 | 2026-05-14 | 0 | official |  |
| H1 | 2026-05-31 | final | 7025872.00 | 2026-06-05 | 2026-06-12 | 0 | official |  |
| H1 | 2026-06-30 | final | 7205032.00 | 2026-07-07 | 2026-07-14 | 0 | official |  |
| H1 | 2026-07-31 | final | 7050000.00 | 2026-08-07 | 2026-08-14 | 0 | official |  |
| H1 | 2026-07-31 | amended | 7012500.00 | 2026-08-20 | 2026-08-14 | 0 | official | Same fund under a second name; replaces 7,050,000 (fee accrual correction of 37,500). |
| H1 | 2026-08-31 | final | 7210000.00 | 2026-09-07 | 2026-09-14 | 0 | official |  |
| H1 | 2026-09-30 | estimate | 7320000.00 | 2026-10-06 | 2026-10-14 | 0 | estimated |  |
| H2 | 2025-10-31 | final | 5026071.00 | 2025-11-07 | 2025-11-14 | 0 | official |  |
| H2 | 2025-11-30 | final | 5060751.00 | 2025-12-05 | 2025-12-12 | 0 | official |  |
| H2 | 2025-12-31 | final | 5107310.00 | 2026-01-07 | 2026-01-14 | 0 | official |  |
| H2 | 2026-01-31 | final | 5249804.00 | 2026-02-06 | 2026-02-13 | 0 | official |  |
| H2 | 2026-02-28 | final | 5401523.00 | 2026-03-06 | 2026-03-13 | 0 | official |  |
| H2 | 2026-03-31 | final | 5252981.00 | 2026-04-07 | 2026-04-14 | 0 | official |  |
| H2 | 2026-04-30 | final | 5313916.00 | 2026-05-07 | 2026-05-14 | 0 | official |  |
| H2 | 2026-05-31 | final | 5412755.00 | 2026-06-05 | 2026-06-12 | 0 | official |  |
| H2 | 2026-06-30 | final | 5279601.00 | 2026-07-07 | 2026-07-14 | 0 | official |  |
| H2 | 2026-07-31 | final | 5217302.00 | 2026-08-07 | 2026-08-14 | 0 | official |  |
| H2 | 2026-08-31 | final | 5090000.00 | 2026-09-22 | 2026-09-14 | 6 | official |  |
| H2 | 2026-09-30 | estimate | 5180000.00 | 2026-10-07 | 2026-10-14 | 0 | estimated |  |
| L1 | 2025-10-31 | final | 6264500.00 | 2025-11-03 | 2025-11-14 | 0 | official |  |
| L1 | 2025-11-30 | final | 6290000.00 | 2025-12-01 | 2025-12-12 | 0 | official |  |
| L1 | 2025-12-31 | final | 6334500.00 | 2026-01-01 | 2026-01-14 | 0 | official |  |
| L1 | 2026-01-31 | final | 6418500.00 | 2026-02-02 | 2026-02-13 | 0 | official |  |
| L1 | 2026-02-28 | final | 6558000.00 | 2026-03-02 | 2026-03-13 | 0 | official |  |
| L1 | 2026-03-31 | final | 6454500.00 | 2026-04-01 | 2026-04-14 | 0 | official |  |
| L1 | 2026-04-30 | final | 6397500.00 | 2026-05-01 | 2026-05-14 | 0 | official |  |
| L1 | 2026-05-31 | final | 6178500.00 | 2026-06-01 | 2026-06-12 | 0 | official |  |
| L1 | 2026-06-30 | final | 6024000.00 | 2026-07-01 | 2026-07-14 | 0 | official |  |
| L1 | 2026-07-31 | final | 6094000.00 | 2026-08-03 | 2026-08-14 | 0 | official |  |
| L1 | 2026-08-31 | final | 6161000.00 | 2026-09-01 | 2026-09-14 | 0 | official |  |
| L1 | 2026-09-30 | final | 6150000.00 | 2026-10-01 | 2026-10-14 | 0 | official |  |
| L2 | 2025-10-31 | final | 4180000.00 | 2025-11-03 | 2025-11-14 | 0 | official |  |
| L2 | 2025-11-30 | final | 4170400.00 | 2025-12-01 | 2025-12-12 | 0 | official |  |
| L2 | 2025-12-31 | final | 4154000.00 | 2026-01-01 | 2026-01-14 | 0 | official |  |
| L2 | 2026-01-31 | final | 4172800.00 | 2026-02-02 | 2026-02-13 | 0 | official |  |
| L2 | 2026-02-28 | final | 4130400.00 | 2026-03-02 | 2026-03-13 | 0 | official |  |
| L2 | 2026-03-31 | final | 4162400.00 | 2026-04-01 | 2026-04-14 | 0 | official |  |
| L2 | 2026-04-30 | final | 4118400.00 | 2026-05-01 | 2026-05-14 | 0 | official |  |
| L2 | 2026-05-31 | final | 4158400.00 | 2026-06-01 | 2026-06-12 | 0 | official |  |
| L2 | 2026-06-30 | final | 4124800.00 | 2026-07-01 | 2026-07-14 | 0 | official |  |
| L2 | 2026-07-31 | final | 4119200.00 | 2026-08-03 | 2026-08-14 | 0 | official |  |
| L2 | 2026-08-31 | final | 4084000.00 | 2026-09-01 | 2026-09-14 | 0 | official |  |
| L2 | 2026-09-30 | final | 4100000.00 | 2026-10-01 | 2026-10-14 | 0 | official |  |

## Administrator NAV per portfolio per month (investment view known now in brackets)

| Month end | EG-GROWTH | EG-LIQUID | EG-B-OPS | EG-FUNDS |
|---|---|---|---|---|
| 2025-10-31 | 0.00 (13635700.00) | 40216100.00 (40216100.00) | 20700000.00 (20700000.00) | 10444500.00 (22423615.00) |
| 2025-11-30 | 13635700.00 (13907278.00) | 40112500.00 (40112500.00) | 20700000.00 (20700000.00) | 22439515.00 (22596569.00) |
| 2025-12-31 | 13907278.00 (14111511.00) | 39970900.00 (39970900.00) | 20700000.00 (21200000.00) | 22624669.00 (22726416.00) |
| 2026-01-31 | 14111511.00 (14050375.00) | 40173000.00 (40173000.00) | 21200000.00 (21200000.00) | 22829216.00 (22976701.00) |
| 2026-02-28 | 14386201.00 (14421848.00) | 39953600.00 (39953600.00) | 21200000.00 (21200000.00) | 23073801.00 (23090657.00) |
| 2026-03-31 | 14473864.00 (14594384.00) | 39717300.00 (39717300.00) | 21200000.00 (22050000.00) | 23019157.00 (22907019.00) |
| 2026-04-30 | 14598965.00 (14818012.00) | 39598100.00 (39598100.00) | 22050000.00 (22050000.00) | 22806019.00 (22870473.00) |
| 2026-05-31 | 14818012.00 (14812017.00) | 39685700.00 (39685700.00) | 22050000.00 (22050000.00) | 22691473.00 (22775527.00) |
| 2026-06-30 | 14812017.00 (15218938.00) | 39806800.00 (39806800.00) | 22050000.00 (22525000.00) | 22587427.00 (22633433.00) |
| 2026-07-31 | 15218938.00 (15450680.00) | 39819400.00 (39819400.00) | 22670000.00 (22525000.00) | 22697833.00 (22443002.00) |
| 2026-08-31 | 15416000.00 (15416000.00) | 39552000.00 (39552000.00) | 22525000.00 (22525000.00) | 22474802.00 (22545000.00) |
| 2026-09-30 | 16400000.00 (16580000.00) | 41200000.00 (41200000.00) | 22525000.00 (22875000.00) | 22550000.00 (22750000.00) |

## NAV bridge at 30 Sep 2026

| Portfolio | Administrator NAV | Investment view | Revisions | Timing | FX | Unexplained | Parts |
|---|---|---|---|---|---|---|---|
| EG-GROWTH | 16400000.00 | 16580000.00 | 180000.00 | 0.00 | 0.00 | 0.00 | A revision 180000.00 |
| EG-LIQUID | 41200000.00 | 41200000.00 | 0.00 | 0.00 | 0.00 | 0.00 |  |
| EG-B-OPS | 22525000.00 | 22875000.00 | 350000.00 | 0.00 | 0.00 | 0.00 | E revision 350000.00 |
| EG-FUNDS | 22550000.00 | 22750000.00 | 200000.00 | 0.00 | 0.00 | 0.00 | H1 revision 110000.00; H2 revision 90000.00 |

## Cash on 8 Oct 2026 (two views; the daily file has 30 days)

| Entity | Administrator | Trading export | Difference | Over 5,000? |
|---|---|---|---|---|
| EG-HOLD | 2300000.00 | 2300000.00 | 0.00 | False |
| EG-TRUST | 1150000.00 | 1148200.00 | 1800.00 | False |
| EG-B | 880400.00 | 868000.00 | 12400.00 | True |

Cash activity: 232 items (fees, coupons, FX settlements, sweeps) from opening balances at the close of 8 Sep; they sum to the daily balances on each side. Every item is booked the same day on both sides except these:

| Reference | Entity | Amount | Administrator | Trading export | Bank | What |
|---|---|---|---|---|---|---|
| WIRE-20261008-B01 | EG-B | -12400.00 | 2026-10-09 | 2026-10-08 | 2026-10-08 | Legal fees, Saltmarsh Infrastructure Fund II |
| CHG-20261006-T01 | EG-TRUST | -1800.00 | never | 2026-10-06 | never | Custody charge, booked by the trading desk only |

## Commitments

| Fund | Entity | Commitment | Called to date | Uncalled | Noticed / due later |
|---|---|---|---|---|---|
| A | EG-HOLD | 15000000.00 | 11250000.00 | 3750000.00 | 0.00 |
| B | EG-HOLD | 8000000.00 | 7200000.00 | 800000.00 | 0.00 |
| C | EG-B | 6000000.00 | 3600000.00 | 2400000.00 | 450000.00 |
| D | EG-B | 5000000.00 | 4500000.00 | 500000.00 | 250000.00 |
| E | EG-B | 10000000.00 | 4000000.00 | 6000000.00 | 600000.00 |

## Calls and distributions (Aug 2025 to Dec 2026)

| Id | Fund | Kind | Amount | Notice | Due | Status | Days from 9 Oct |
|---|---|---|---|---|---|---|---|
| mv-2025-08-A-call | A | call | 250000.00 | 2025-08-04 | 2025-08-20 | confirmed | -415 |
| mv-2025-09-E-call | E | call | 600000.00 | 2025-09-08 | 2025-09-25 | confirmed | -379 |
| mv-2025-10-C-call | C | call | 300000.00 | 2025-10-06 | 2025-10-24 | confirmed | -350 |
| mv-2025-11-B-call | B | call | 400000.00 | 2025-11-03 | 2025-11-19 | confirmed | -324 |
| mv-2025-12-A-dist | A | distribution | 275000.00 | 2025-12-01 | 2025-12-18 | confirmed | -295 |
| mv-2026-01-D-call | D | call | 300000.00 | 2026-01-12 | 2026-01-29 | confirmed | -253 |
| mv-2026-02-E-call | E | call | 600000.00 | 2026-02-09 | 2026-02-26 | confirmed | -225 |
| mv-2026-03-A-call | A | call | 500000.00 | 2026-03-02 | 2026-03-19 | confirmed | -204 |
| mv-2026-04-C-call | C | call | 300000.00 | 2026-04-06 | 2026-04-23 | confirmed | -169 |
| mv-2026-05-B-call | B | call | 400000.00 | 2026-05-04 | 2026-05-21 | confirmed | -141 |
| mv-2026-06-C-call | C | call | 300000.00 | 2026-06-08 | 2026-06-25 | confirmed | -106 |
| mv-2026-07-D-call | D | call | 300000.00 | 2026-07-06 | 2026-07-23 | confirmed | -78 |
| mv-2026-09-D-dist | D | distribution | 180000.00 | 2026-09-01 | 2026-09-15 | confirmed | -24 |
| mv-2026-10-C-call | C | call | 450000.00 | 2026-10-02 | 2026-10-20 | confirmed | 11 |
| mv-2026-10-E-call | E | call | 600000.00 | 2026-10-06 | 2026-10-30 | noticed | 21 |
| mv-2026-11-A-dist | A | distribution | 320000.00 | 2026-10-05 | 2026-11-16 | noticed | 38 |
| mv-2026-12-D-call | D | call | 250000.00 | 2026-10-01 | 2026-12-04 | confirmed | 56 |

## Liquidity at 9 Oct

| Entity | Available (admin 8 Oct) | Calls 30d | Calls 60d | Calls 90d | Distributions 60d | After confirmed calls | After all noticed calls | Unconfirmed |
|---|---|---|---|---|---|---|---|---|
| EG-HOLD | 2300000.00 | 0.00 | 0.00 | 0.00 | 320000.00 | 2300000.00 | 2300000.00 |  |
| EG-TRUST | 1150000.00 | 0.00 | 0.00 | 0.00 | 0.00 | 1150000.00 | 1150000.00 |  |
| EG-B | 880400.00 | 1050000.00 | 250000.00 | 0.00 | 0.00 | 430400.00 | -169600.00 | mv-2026-10-E-call |

## Trades 1 to 8 Oct 2026 (trading export vs administrator)

| Id | Date | Side | Security | Quantity | Price | Amount | Admin quantity | Result | Planted |
|---|---|---|---|---|---|---|---|---|---|
| T-20261001-001 | 2026-10-01 | buy | MRF | 20000 | 33.10 | 662000.00 | 20000 | matched |  |
| T-20261002-002 | 2026-10-02 | sell | BSU | 10000 | 48.20 | 482000.00 | 10000 | matched |  |
| T-20261002-003 | 2026-10-02 | buy | NWL | 12000 | 42.15 | 505800.00 | 10200 | break | quantity mismatch |
| T-20261006-005 | 2026-10-06 | sell | HVS | 5000 | 118.40 | 592000.00 | missing | break | missing at administrator |
| T-20261007-006 | 2026-10-07 | buy | CRB31 | 1000000 | 0.9910 | 991000.00 | 1000000 | matched |  |
| T-20261005-004 | 2026-10-05 | sell USD / buy SGD | FXF-2026-002 | 3000000.00 | 1.3425 | 4027500.00 | 3000000.00 | break | FX forward confirmation rate mismatch |

## Limits at 30 Sep 2026

| Rule | Portfolio | Dimension | Bucket | Min | Max | Exposure % | Result | Cause |
|---|---|---|---|---|---|---|---|---|
| limit_single_name_liquid | EG-LIQUID | single_name | Harborview Semiconductor | 0 | 5 | 5.75 | breach | real |
| limit_listed_equity_liquid | EG-LIQUID | asset_class | listed_equity | 60 | 90 | 80.61 | within |  |
| limit_manager_entity_b | EG-B-OPS | manager | Cedarpoint Ventures | 0 | 55 | 56.50 | breach | stale data |
| limit_hedge_funds | EG-FUNDS | asset_class | hedge_fund | 20 | 60 | 54.95 | within |  |

## Benchmark

`EG-OFFICE-BLEND` Evergreen office benchmark, v1 approved (equity 0.42, bonds 0.28, private sleeve 0.30 = equity + 300 bps), v2 in_progress (0.36/0.24/0.40). Liquid sleeve alone: 60% equity, 40% bonds.

| September 2026 | % |
|---|---|
| equity_index_return_pct | 3.5002 |
| bond_index_return_pct | 0.4002 |
| private_sleeve_return_pct | 3.7502 |
| blend_v1_return_pct | 2.7072 |
| sixty_forty_return_pct | 2.2602 |
| eg_liquid_portfolio_return_pct | 4.1667 |
| eg_liquid_minus_sixty_forty_pct | 1.9065 |

Index month-end anchors:

| Month end | Global Equity Index (synthetic) | Global Bond Index (synthetic) | USD/SGD WMR 4pm |
|---|---|---|---|
| 2025-09-30 | 1000.00 | 1000.00 | 1.3138 |
| 2025-10-31 | 978.00 | 1006.10 | 1.3087 |
| 2025-11-30 | 996.48 | 1016.97 | 1.3006 |
| 2025-12-31 | 986.81 | 1014.02 | 1.3162 |
| 2026-01-31 | 1011.58 | 1019.29 | 1.3275 |
| 2026-02-28 | 1004.20 | 1025.10 | 1.3333 |
| 2026-03-31 | 1004.00 | 1032.89 | 1.3454 |
| 2026-04-30 | 982.82 | 1029.27 | 1.3298 |
| 2026-05-31 | 1019.77 | 1028.45 | 1.3454 |
| 2026-06-30 | 1009.06 | 1036.78 | 1.3344 |
| 2026-07-31 | 1026.62 | 1031.60 | 1.3420 |
| 2026-08-31 | 1038.22 | 1037.07 | 1.3263 |
| 2026-09-30 | 1074.56 | 1041.22 | 1.3412 |

## Signed rules

| Code | Type | Owner | Parameters | Words |
|---|---|---|---|---|
| cash_tolerance | tolerance | Raj Patel | {"abs_amount": 5000, "currency": "USD", "per": "entity_day"} | Cash may differ by up to 5,000 USD per entity per day before it needs a case. |
| cio_materiality | materiality | Raj Patel | {"abs_amount": 100000, "pct_of_fund": 0.5, "currency": "USD"} | The CIO sees a change over 100,000 USD or 0.5% of a fund. |
| estimate_use | policy | Raj Patel | {"allowed_in": ["investment_report"]} | A manager estimate may be used in the investment report only. |
| statement_due | deadline | Mei Chen | {"business_days_after_month_end": 10} | A manager statement is due within 10 business days of the period end. |
| fx_fixing | fixing | Raj Patel | {"fixing": "WMR_4PM", "series_key": "FX:USDSGD:WMR_4PM"} | Convert with the WMR 4pm USD/SGD fixing in the market data file. |
| cash_call_alert_days | deadline | Raj Patel | {"days": 30} | A confirmed capital call due within 30 days opens a Finance case to fund it. |
| limit_single_name_liquid | limit | Sofia Reyes | {"dimension": "single_name", "bucket": "Harborview Semiconductor", "min_pct": 0.0, "max_pct": 5.0, "portfolio_code": "EG-LIQUID"} | EG-LIQUID: Harborview Semiconductor must be between 0% and 5% of the portfolio. |
| limit_listed_equity_liquid | limit | Sofia Reyes | {"dimension": "asset_class", "bucket": "listed_equity", "min_pct": 60.0, "max_pct": 90.0, "portfolio_code": "EG-LIQUID"} | EG-LIQUID: asset_class 'listed_equity' between 60% and 90% of the portfolio. |
| limit_manager_entity_b | limit | Sofia Reyes | {"dimension": "manager", "bucket": "Cedarpoint Ventures", "min_pct": 0.0, "max_pct": 55.0, "portfolio_code": "EG-B-OPS"} | EG-B-OPS: manager 'Cedarpoint Ventures' between 0% and 55% of the portfolio. |
| limit_hedge_funds | limit | Sofia Reyes | {"dimension": "asset_class", "bucket": "hedge_fund", "min_pct": 20.0, "max_pct": 60.0, "portfolio_code": "EG-FUNDS"} | EG-FUNDS: asset_class 'hedge_fund' between 20% and 60% of the portfolio. |

## Documents (library)

| Id | Manager | Type | Date | Title | Key facts |
|---|---|---|---|---|---|
| doc-note-01 | MGR-NORTHGATE | meeting_note | 2026-02-11 | Northgate Partners annual meeting notes | Fund A expects two exits in 2026. Distribution of about 300,000 USD guided for Q4 2026. |
| doc-note-02 | MGR-BLUEWATER | meeting_note | 2026-04-22 | Bluewater Capital quarterly call | Fund B portfolio yield 9.1%. No defaults in the book. |
| doc-note-03 | MGR-CEDARPOINT | meeting_note | 2026-05-19 | Cedarpoint Ventures LP update call | Cedarpoint Ventures III: one portfolio company raising at a lower valuation. Cedarpoint Opportunities II reporting delayed by an auditor change. |
| doc-note-04 | MGR-KESTREL | meeting_note | 2026-06-12 | Kestrel Ridge Advisors on-site meeting | Macro fund run by two co-portfolio managers. Fee accruals reviewed monthly. |
| doc-note-05 | MGR-SALTMARSH | meeting_note | 2026-07-30 | Saltmarsh Real Assets Q2 call | Infrastructure Fund II: two new assets; a 600,000 USD call expected in Q4 2026. |
| doc-note-06 | MGR-MERIDIAN | meeting_note | 2026-08-26 | Meridian Index Managers service review | Daily pricing file to move to a new format in 2027. |
| doc-ddq-01 | MGR-KESTREL | ddq | 2026-01-20 | Kestrel Ridge Advisors DDQ 2026 | Firm assets 2.4 bn USD (synthetic). Macro fund portfolio managers: Thomas Lindqvist, Priya Nair. |
| doc-ddq-02 | MGR-CEDARPOINT | ddq | 2026-03-05 | Cedarpoint Ventures DDQ 2026 | Quarterly statements within 45 days of quarter end; under its side letter Evergreen Office receives them within 10 business days. Auditor change effective Q2 2026. |
| doc-news-01 | MGR-KESTREL | newsletter | 2026-09-28 | Kestrel Ridge Advisors Q3 2026 newsletter | Team change: Thomas Lindqvist left the firm on 30 September 2026; Priya Nair is sole portfolio manager of the Macro Fund from 1 October 2026. |
| doc-news-02 | MGR-NORTHGATE | newsletter | 2026-07-15 | Northgate Partners mid-year letter | Fund A: one exit signed, closing expected Q4 2026. |
| doc-ic-01 |  | ic_note | 2026-09-17 | Evergreen investment committee note, September 2026 | Harborview Semiconductor above the 5% single-name limit; desk to trim. Benchmark re-weighting to be proposed by Risk. |

## Month-end process (signed intent, UC9)

| # | Step | Who | System | Manual | Control | Exception |
|---|---|---|---|---|---|---|
| 1 | Collect the exports | Mei Chen | File drop | True | Row count and file totals agree with the control totals of the file. | A rejected file is re-requested the same day. |
| 2 | Check cash against the administrator | Mei Chen | Excel | True | Difference per entity per day within the cash tolerance of 5,000 USD. | Over tolerance opens a break case (Entity B, 12,400 USD on 8 Oct 2026). |
| 3 | Collect manager statements | Mei Chen | Email | True | Every expected statement received within 10 business days of the period end. | Late or missing: follow-up draft to the manager. |
| 4 | Convert to SGD | Raj Patel | Excel | True | Converted at the WMR 4pm USD/SGD fixing of the period end. | No fixing: hold the report. |
| 5 | Review and approve the report | Raj Patel | Report pack | False | Maker never checker; a manager estimate is used in the investment report only. | A revision over the CIO materiality threshold (100,000 USD or 0.5% of a fund) reopens the review. |
| 6 | Read the report | Daniel Foo | Report pack | False | Issued version with cutoff shown. | Questions to managers logged as open questions. |

## Planted facts (the answer key)

| Id | UC | Fact | Expected | Where | Role |
|---|---|---|---|---|---|
| P01 | UC1 | September report as issued | A 10,000,000 (estimated), B 6,400,000, Evergreen Liquid Book 41,200,000, total 57,600,000 USD; issued 3 Oct 2026 10:30, cutoff 3 Oct 10:00; SGD total 77,253,120.00 at 1.3412 | Consume > Office view > Issued vs known now; CIO Brief | sponsor |
| P02 | UC1 | Fund A amended statement (known now) | 10,180,000 USD, received 7 Oct 2026; +180,000 (1.80%) over the issued 10,000,000; over cio_materiality (100,000 USD / 0.5%); status word Revised | Consume > Office view > Issued vs known now; Today card 'Revised'; CIO Brief | sponsor |
| P03 | UC1 | NAV bridge EG-GROWTH 30 Sep | Investment view 16,580,000 vs administrator NAV 16,400,000: revisions +180,000 (Fund A), timing 0, FX 0, unexplained 0 | Consume > Office view > NAV bridge | sponsor |
| P04 | UC1 | NAV bridge EG-B-OPS 30 Sep | Investment view 22,875,000 vs administrator NAV 22,525,000: revisions +350,000 (Fund E Q3 statement recorded 8 Oct, after the NAV of 2 Oct); timing 0 | Consume > Office view > NAV bridge | sponsor |
| P05 | UC1 | NAV bridge EG-FUNDS 30 Sep | Investment view 22750000.00 vs administrator NAV 22550000.00: revisions 200000.00 (H1 and H2 September estimates received 6 and 7 Oct, after the NAV of 2 Oct); timing 0 | Consume > Office view > NAV bridge | sponsor |
| P06 | UC1 | Why did this move: liquid book Aug to Sep | 39,552,000 to 41,200,000 USD, +1,648,000 (+4.1667%); no trades in September; largest contributor shown per security from the monthly prices | Consume > Office view > Why did this move | sponsor |
| P07 | UC1 | Holdings status words at 30 Sep | A Revised (after the amended statement; Estimated before), B Official, C Stale (30 Jun 2026 amended value, 101 days), D Stale (31 Mar 2026, 192 days), E Unverified (9,950,000 extracted, not confirmed), H1/H2 Estimated, L1/L2 Official, PRC29 'Needs a class' | Consume > Office view > Holdings | analyst |
| P08 | UC2 | Entity B cash break 8 Oct | Administrator 880,400 vs trading export 868,000: 12,400 USD over the 5,000 tolerance; one break case. Trust 1,150,000 vs 1,148,200 (1,800, inside tolerance, no case). Holdings 2,300,000 both views. | Action > Reconciliations (cash) and Cases | analyst, approver |
| P08b | UC2 | Entity B cash break cause: one wire booked a day apart | Tally ranks WIRE-20261008-B01, 12,400 USD (legal fees, Saltmarsh Infrastructure Fund II), first: paid and booked by the trading desk on 8 Oct (the bank agrees, 868,000), booked by the administrator on 9 Oct: a timing difference that clears when the administrator books it. Every other item of the 30 days is booked the same day on both sides; the Trust's 1,800 is one charge booked by the trading desk only (CHG-20261006-T01). | Action > Cases > Cash differs · Entity B · 2026-10-08 > Tally | analyst |
| P09 | UC3 | September statements expected vs received at 9 Oct | Due 14 Oct 2026 (10 business days). Received: A estimate 2 Oct, B final 1 Oct, E final 8 Oct (unverified), H1 estimate 6 Oct, H2 estimate 7 Oct, L1 and L2 1 Oct. Waiting, not yet late: C, D. | Action > Managers | analyst |
| P10 | UC3 | Late statements | H2 August 2026: due 14 Sep, received 22 Sep, 6 business days late. E June 2026: due 14 Jul, received 24 Jul, 8 business days late. (Also D March 2026: due 14 Apr, received 21 Apr, 5 business days late.) | Action > Managers > late | analyst |
| P11 | UC3 | Missing statement | Cedarpoint Opportunities II (Fund D) 30 June 2026: due 14 Jul 2026, never received, 63 business days overdue at 9 Oct. Follow-up draft addressed to Hana Sato, Cedarpoint Ventures, names the fund and the period; never sent by the product. | Action > Managers > missing; Draft a follow-up | analyst |
| P12 | UC3 | Revised statements (3) | A 30 Sep: 10,000,000 to 10,180,000 (+180,000). C 30 Jun: 8,420,000 to 8,275,000 (-145,000, 18 Aug). H1 31 Jul: 7,050,000 to 7,012,500 (-37,500, 20 Aug). | Action > Managers > revised; Consume > Managers > statements timeline | analyst |
| P13 | UC3 | Same fund under two names | 'KR Macro Fund Ltd - Class B USD' (July amended statement) and 'Kestrel Ridge Macro Fund' are one fund (H1, administrator code 4481); Fund B appears as 'Fund B - Evergreen Liquid Book' and 'Evergreen Income II'. The inbox shows one row per fund, never two. | Action > Managers; Settings > identifiers | analyst |
| P14 | UC4 | Benchmark v1 September 2026 | Equity index 3.5002%, bond index 0.4002%, private sleeve 3.7502% (equity + 25 bps a month); blend v1 (0.42/0.28/0.30) 2.7072%; 60/40 liquid sleeve 2.2602%; EG-LIQUID 4.1667%, difference to 60/40 1.9065 points | Consume tile 'portfolio vs benchmark'; Build plan gold_investment_report_benchmark_monthly | approver |
| P15 | UC4 | Benchmark v2 In Progress | Version 2 (0.36/0.24/0.40, proposed 1 Oct 2026 by Sofia Reyes) is in_progress: refused for certified output and shown as a policy question; certified figures use v1. | Build > benchmark; Settings > Rules | approver |
| P16 | UC4 | SGD conversion | USD figures at 30 Sep convert at 1.3412 (WMR 4pm, fx_fixing); 8 Oct fixing 1.3388. Total 57,600,000 USD = 77,253,120.00 SGD. | Consume > Office view (USD/SGD switch) | approver |
| P17 | UC5 | Real limit breach | EG-LIQUID single name max 5%: Harborview Semiconductor 2,368,000 of 41,200,000 = 5.75%; case limit_breach, cause 'real breach'. (The desk sold 5,000 shares on 6 Oct; the administrator has not booked it.) | Action > Reconciliations > Limits; Cases | participant, analyst |
| P18 | UC5 | Limit breach caused by a stale valuation | EG-B-OPS manager Cedarpoint Ventures max 55%: C 8,275,000 + D 4,650,000 = 12,925,000 of 22875000.00 = 56.50%; case limit_breach, cause 'stale data' (Fund D valued 31 Mar 2026, 192 days old, June statement missing; Fund C's 30 Jun value is 101 days old). | Action > Reconciliations > Limits; Cases | participant, analyst |
| P19 | UC5 | Instrument without asset class | Pacific Rim Convertible 2029 note (PRC29) has no asset_class; 1,122,000 USD = 2.72% of EG-LIQUID; shown as a classification question ('Needs a class'), counted in no bucket, no breach. | Action > Reconciliations > Limits; Settings > instruments | participant |
| P20 | UC5 | Limits within range | EG-LIQUID listed_equity 80.61% (60-90); EG-FUNDS hedge_fund 54.95% (20-60). No case. | Action > Reconciliations > Limits | participant |
| P21 | UC6 | Capital calls due within 30 days | Fund C 450,000 USD due 20 Oct 2026 (notice 2 Oct, confirmed) and Fund E 600,000 USD due 30 Oct 2026 (notice 6 Oct, noticed, NOT confirmed, flagged). Both Entity B. | Consume > Office view > Liquidity; Action > Cases (Finance) | approver |
| P22 | UC6 | Entity B after-call cash | Available 880,400 (administrator, 8 Oct). After the confirmed call: 430,400. After both noticed calls: -169,600 (shortfall). Finance case 'Fund the capital call' opened for the Fund C call (due within cash_call_alert_days = 30). | Consume > Office view > Liquidity; Action > Cases | approver |
| P23 | UC6 | Calls and distributions 60/90 days | Fund D call 250,000 due 4 Dec 2026 (confirmed, 60-day bucket, Entity B). Fund A distribution 320,000 expected 16 Nov 2026 (noticed, Evergreen Holdings). | Consume > Office view > Liquidity | approver |
| P24 | UC6 | Commitments register | A 15000000.00 committed, 11250000.00 called, 3750000.00 uncalled; B 8000000.00 committed, 7200000.00 called, 800000.00 uncalled; C 6000000.00 committed, 3600000.00 called, 2400000.00 uncalled; D 5000000.00 committed, 4500000.00 called, 500000.00 uncalled; E 10000000.00 committed, 4000000.00 called, 6000000.00 uncalled. Called never exceeds commitment. | Consume > Managers > profile; Office view > Liquidity | approver |
| P25 | UC7 | Newsletter team change | Kestrel Ridge Advisors Q3 2026 newsletter (28 Sep 2026): Thomas Lindqvist left on 30 Sep 2026; Priya Nair sole portfolio manager of the Macro Fund from 1 Oct 2026. Shown with the source chip; the product never says whether this is good or bad. | Consume > Managers > Kestrel Ridge Advisors | sponsor, analyst |
| P26 | UC7 | What changed since the last meeting (Kestrel Ridge, 12 Jun 2026) | Statement: July 2026 NAV amended on 20 Aug 2026 from 7,050,000 to 7,012,500 USD (fee accrual). | Statement: August 2026 statement for the Equity Long/Short Fund received 22 Sep 2026, 6 business days late (due 14 Sep). | Newsletter 28 Sep 2026: Thomas Lindqvist left; Priya Nair sole portfolio manager of the Macro Fund from 1 Oct 2026. | Consume > Managers > 'What changed since the last meeting?' | sponsor |
| P27 | UC7 | Cedarpoint Ventures profile | Funds C and D; commitments 6,000,000 and 5,000,000; D last valuation 31 Mar 2026 (stale), June statement missing; DDQ says quarterly statements within 45 days (10 business days for Evergreen Office under its side letter) and an auditor change in Q2 2026; open question: June statement. | Consume > Managers > Cedarpoint Ventures | sponsor, analyst |
| P28 | UC8 | Trade break: quantity mismatch | T-20261002-003 buy Northwind Logistics: trading export 12,000 at 42.15, administrator 10,200; 1,800 shares = 75,870.00 USD, over the 5,000 tolerance; break case. | Action > Reconciliations > trade_vs_admin; Cases | analyst |
| P29 | UC8 | Trade break: missing at the administrator | T-20261006-005 sell 5,000 Harborview Semiconductor at 118.40 (592,000.00 USD) is in the trading export and not at the administrator; break case. | Action > Reconciliations > trade_vs_admin; Cases | analyst |
| P30 | UC8 | FX forward confirmation mismatch | FXF-2026-002 sell USD 3,000,000 / buy SGD: trading export rate 1.3425 (SGD 4,027,500.00), counterparty confirmation 1.3452 (SGD 4,035,600.00); difference SGD 8,100.00 = USD 6050.19 at 1.3388, over tolerance; break case. FXF-2026-001 matches. | Action > Reconciliations > trade_vs_admin; Cases | analyst |
| P31 | UC8 | Matched trades | T-20261001-001, T-20261002-002, T-20261007-006 match on external_trade_id and amount: no case. | Action > Reconciliations > trade_vs_admin | analyst |
| P32 | UC9 | SOP from the signed process map | 6 steps with owner, system, input, output, control and exception; 4 manual steps flagged for automation: 1 Collect the exports (File drop), 2 Check cash against the administrator (Excel), 3 Collect manager statements (Email), 4 Convert to SGD (Excel); hand-overs 1-2, 2-3, 3-4, 4-5, 5-6; download as .docx or .md. | Intent > signed intent 'Monthly investment report in USD and SGD' > Download the SOP | sponsor |
| P33 | UC10 | Pipeline and dashboard | Project 'Monthly investment report in USD and SGD' live: bronze_administrator_positions, bronze_trading_export_positions; gold_investment_report_holdings_monthly, gold_investment_report_cash_daily; dashboard dash-0ad2b1c7 with 3 accepted tiles (K01 Net worth by entity, K02 Cash by entity, K03 Holdings by status) shared with Daniel Foo and Raj Patel. | Intent > Build > Consume | analyst |
