Synthetic, illustrative. NOT a client document: answer key for tests and demos. Never seeded into company context.

# 18 - Answer key: ambiguities planted in 16 and 17

Entry names are as written in 16_business_glossary_raw.md (G) or 17_technical_notes_raw.md (T).

| # | Ambiguity | Where | Why it matters for building | Question a business analyst should ask |
|---|---|---|---|---|
| 1 | Net or gross of fees not stated | G Alpha; G Manager scorecard | Excess return changes with fees; the pack measure is net of fees | Is the fund return net or gross of fees, and which fees? |
| 2 | Period end: month end vs last business day | G Unfunded commitments ("last business day") vs G Old valuations and Value bridge ("month end") | Different cut-off dates give different balances and ages | Which date is the reporting date for each measure? |
| 3 | Currency basis and FX rate date not stated | G Known obligations ("in SGD"); G Cash cushion; T Cash cushion ("ask Tom") | Conversion changes totals; USD calls settle at T+2 | Which rate, from where, on which date? |
| 4 | Two owners for one measure | G Exposure (single name): Wei Chen and Mei Tan | Nobody can approve a definition change | Who is the one owner who signs the definition? |
| 5 | Definition contradicts the capital-call procedure | G Known obligations ("once it has been paid") vs 07 (current, unpaid, notified calls count) | Funding headroom would ignore every unpaid call | Which is right: unpaid notified calls, or paid ones? |
| 6 | Benchmark does not say which index | G Alpha, Manager scorecard, Benchmark cover | The result flips with the index (S&P 500, MSCI World, the manager's own) | Which benchmark per fund, who approves it, who may change it? |
| 7 | Threshold with no number | G Old valuations ("our usual limit"); G Open conflicts ("big enough to matter"); G Stress cash need ("usual multiplier"); G Policy exceptions ("reasonable") | A flag or count cannot be computed | What is the number, per asset class where it differs? |
| 8 | Measure defined by an example only | G Benchmark cover (MGE has one, the infrastructure fund does not) | No rule for new holdings or disputed benchmarks | State the rule: what makes a benchmark agreed? |
| 9 | Same term, two meanings (duplicate term) | G Exposure (single name) vs G Exposure (currency) | One field would carry two calculations | Rename them? Which one is "exposure" in the pack? |
| 10 | Source named differently from the catalogue | G Manager scorecard and Alpha ("the tracker") vs 05 (Performance_Workbook.xlsx); the capital-call tracker is also "the tracker" | The wrong source gets connected | Which file is "the tracker" in each entry? |
| 11 | Amended notices counted once or twice | G Notices to chase ("a corrected notice goes on the list too"); T Notices to chase ("ask Sara"); 07 step 8 | Double counting | Does a corrected notice replace or add? |
| 12 | Headcount basis for the pay measure | G Pay inputs matched ("share of staff"); T (everyone in the Review tab) vs 14 (investment team only) | Wrong denominator | Whose pay inputs are in scope; is the vacant seat counted? |
| 13 | Glossary and note disagree: month bucket | G Known obligations vs T (notice_date; Sara says due_date) | Obligations fall in the wrong month | Which date decides the month? |
| 14 | Glossary and note disagree: age basis | G Old valuations (valuation date against a limit) vs T (quarters from the statement period) | Different stale shares | Days from valuation_date, or quarters? |
| 15 | Glossary and note disagree: source | G Alpha ("the tracker") vs T Alpha (Performance_Workbook.xlsx) | See 10 | Confirm the workbook |
| 16 | "Logged" hours that are not logged | G Pack effort vs 00 (38 hours estimated, none logged) | No data to compute from | Where would hours be logged? |
| 17 | Stale entries and an orphan | G Open conflicts (2023), Private share (2022, predates the co-investment vehicle), Benchmark cover (no owner, 2023) | Definitions may be out of date | Still current? Who owns Benchmark cover? |

## Inputs only people can give

- The approved return method per fund type (time-weighted, net IRR, value change), and net or gross of fees.
- One approved benchmark per fund, who approves it and who may change it.
- The reporting date rule (month end or last business day).
- The FX rate source, time and date, and who types it.
- The staleness limit per asset class, the materiality limit for conflicts, the stress multiplier to use, and what a reasonable waiting time for exceptions is.
- Who owns each term, one name each.
- Whether a corrected notice replaces or adds.
- Whose pay inputs are in scope for the pay measure.
- Who may see the pay file, and whether Finance keeps access.
- Whether the market data vendor and the index provider may be connected, and who holds the licence.
