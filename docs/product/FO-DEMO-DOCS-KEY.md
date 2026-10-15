# Answer key: demo unstructured documents

Outside the product. 24 synthetic documents for the demo company, in `data/<company>/documents/` (copy in `local/documents/<company>/`). File numbers below are the file name prefixes. Fictional parties only.

## Document inventory

| No | Type | Owner | Key facts |
|---|---|---|---|
| 01 to 03 | Custodian statement summary, June, July, August 2026 | Grace Ward | Totals SGD 184,320,500 / 186,905,210 / 188,112,740 across NC-001, NC-002, NC-003 |
| 04 | Capital call, Orchard Growth Partners I | Grace Ward | USD 1,200,000, call 5, due 28 Aug 2026, unfunded after: USD 2,300,000 of 10,000,000 |
| 05 | Capital call, Marina Growth Partners II | Grace Ward | SGD 1,800,000, call 4, due 28 Sep 2026, unfunded after: SGD 3,000,000 of 12,000,000 |
| 06 | Distribution, Sentosa Growth Partners III | Grace Ward | USD 850,000 (600,000 capital, 250,000 gain), paid 10 Jul 2026 |
| 07 | Manager letter, Orchard I, Q2 2026 | Daniel Kerr | NAV USD 11,840,000, family share about USD 1,681,000, quarter +3.1 % |
| 08 | Manager letter, Changi Growth Partners IV, FY2025 | Daniel Kerr | NAV SGD 6,950,000 at 31 Dec 2025, unaudited, no later valuation |
| 09 | Invoice, custody, Q2 2026 | Grace Ward | SGD 26,230 (22,230 + 3,550 + 450) |
| 10 | Invoice, management fee, Marina II, H1 2026 | Grace Ward | SGD 97,400 (90,000 + 7,400), drawn through a call |
| 11 | Invoice, performance fee, Orchard I | Grace Ward | Carry USD 61,500 (SGD 83,640 at 1.36) |
| 12 | Investment policy statement | Meredith Shaw | Targets and ranges, 10 % issuer limit, definitions |
| 13 | Reconciliation and exception policy | Grace Ward | Tolerances, 98 % threshold, exception types |
| 14 | Data access policy | Meredith Shaw | Five roles plus the family reader |
| 15 | Retention note | Grace Ward | 7 years, minutes for life, email saved in 5 business days |
| 16, 17 | Committee minutes, 19 Feb and 21 May 2026 | Grace Ward | Concentration, drift, hedging |
| 18 | Email, price query, 5 Aug 2026 | Grace Ward | Meridian Port Logistics, 3 and 4 Aug |
| 19 | Email, capital call reminder, 24 Aug 2026 | Grace Ward | Orchard call; HB-USD-01 holds USD 1,640,000 |
| 20 | Email, break investigation, 17 Jul 2026 | Daniel Kerr | Straits Telecom Holdings, NC-001, 4,000 units, about SGD 21,000 |
| 21 | Valuation policy, private assets | Daniel Kerr | Stale after 180 days |
| 22 | Benchmark policy | Daniel Kerr | 60 % Straits 50 index, 30 % Pacific Bond Aggregate, 10 % Global Equity Index, monthly rebalance |
| 23 | Fee agreement, Northgate Custody | Grace Ward | 0.06 %, SGD 25 per trade, SGD 150 per event, SGD 15,000 minimum quarter |
| 24 | Systems inventory | Daniel Kerr | Seven systems; names the MB-SGD-02 file stop on 20 Sep 2026 |

## Planted definitions (document 12)
Net worth, TWR, MWR (XIRR), drift (range breach), concentration (per issuer, all instruments), liquidity runway (months of known obligations covered by cash and equivalents).

## Planted tolerances
Document 13: quantity exact; cash the greater of SGD 100 or 0.01 % of balance; market value 0.10 % of account value; at least 98 % of public positions reconcile per date; material exception above SGD 50,000 or any unknown security; stale feed after 09:00 Singapore time next business day. Document 21: stale after 180 days. Document 14: external access ends after 90 days.

## Planted owners
Policies: Meredith Shaw (12, 14). Reconciliation, retention, fee agreement, notices, invoices, minutes: Grace Ward. Valuation, benchmark, systems, manager letters: Daniel Kerr. Tax note in 11 addressed to Harvey Rowley.

## Planted contradiction
The IPS (12) sets the single-issuer limit at **10 %** from 1 Jan 2026. The minutes of 19 Feb 2026 (16) record a decision to raise it to **12 %** until the end of 2026, reaffirmed on 21 May (17) with the IPS to be updated "in due course". The IPS was never changed. Expected platform behaviour: show both, say the minutes are later but the IPS is the approved policy text, ask a human to resolve; do not pick silently. Straits Telecom Holdings was 11.4 % on 13 Feb: a breach under the IPS, within limit under the minutes.

## Planted unclear decision
Minutes 16, item 4: the committee "agreed to look at hedging it more" (USD exposure): no amount, owner, date or instrument. Expected: flagged as an unassigned, unquantified action. A softer second case: minutes 17 item 1, equities at 51.8 % against a 50 % maximum, "wait for the half-year", no trade and no date.

## Cross-document links a reader should make
- Break (20) and July statement (02): the same 4,000 units, 15 Jul 2026.
- Missing price (18) and August statement (03): 3 and 4 Aug, Meridian Port Logistics.
- Unknown security: June statement (01), ISIN SG9999000123 in NC-002 on 30 Jun.
- Stale valuation (08, 21): Changi IV passes 180 days on 29 Jun 2026; also raised in minutes 17.
- Stale bank file (24): MB-SGD-02 stops 20 Sep 2026.
- Capital call 04 is funded per statement 03 (28 Aug) and email 19. Unfunded: Orchard I USD 2,300,000, Marina II SGD 3,000,000.
- Custody invoice (09) checks against fee agreement (23): 0.06 % x 148,200,000 / 4 = 22,230.
- Distribution (06) shows in the July statement (02) as received in the bank account, not at the custodian.
- Equities above maximum from May (17) and concentration above 10 % from February (16) match the drift and concentration plants in the structured data.

## Questions with exact answers
1. Who owns the reconciliation policy? Grace Ward; approver Meredith Shaw.
2. What is the reconciliation pass threshold? 98 % of public positions on quantity and cash.
3. What is the cash tolerance? The greater of SGD 100 or 0.01 % of the account balance.
4. When is a private valuation stale, and which fund is? After 180 days; Changi Growth Partners IV (31 Dec 2025).
5. What is due on 28 August 2026? Orchard I call 5, USD 1,200,000.
6. What is Marina II unfunded after call 4? SGD 3,000,000.
7. What was the July 2026 break? One missing sale of 4,000 Straits Telecom Holdings units on 15 Jul in NC-001, about SGD 21,000.
8. What is the single-issuer limit? Contradiction: 10 % (IPS) or 12 % (minutes). Both must be shown.
9. What is the benchmark? 60 % Straits 50 index, 30 % Pacific Bond Aggregate, 10 % Global Equity Index, rebalanced monthly.
10. Can the tax adviser see committee minutes? No. Can the external adviser see bank data? No.
11. What was total custodian value at 31 Aug 2026? SGD 188,112,740.
12. What is the custody fee for Q2 2026? SGD 26,230.

## Names used (to match the structured data)
Northgate Custody (NC-001, NC-002, NC-003); Harbour Bank (HB-USD-01); Meridian Bank (MB-SGD-02); Straits 50 index; funds Orchard Growth Partners I, Marina Growth Partners II, Sentosa Growth Partners III, Changi Growth Partners IV; securities Straits Telecom Holdings and Meridian Port Logistics; two legal entities, a family trust and a holding company.
