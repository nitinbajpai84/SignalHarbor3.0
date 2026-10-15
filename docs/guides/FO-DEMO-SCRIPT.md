# The family-office demo on Signal Harbor 1.0 (8 October 2026)

The demo company is the second 1.0 workspace (`ardmore-1`; its display name lives only in `data/`). Its data was made for the product requirements document in `docs/product/FAMILY-OFFICE-PRD.md`: the P0 sources of section 7, the canonical model of section 8, and the phase 1 use cases, with the phase 2 items as offers. Ten planted truths (reconciliation break, missing price, unknown security, duplicate, stale file, out-of-balance cash, stale private valuation, allocation drift, concentration breach, a reproducible Q2 return) are listed with exact values in `docs/product/FO-DEMO-ANSWER-KEY.md`; the documents' plants in `docs/product/FO-DEMO-DOCS-KEY.md`. Neither key is in the product.

Server: http://localhost:8400. Sign-ins in `data/_control/seed_credentials.txt` (this repo's file).

| Who | Sign-in | PRD role | Seat |
|---|---|---|---|
| Meredith Shaw | `meredith.shaw.ardmore-1@example.test` | Principal / CIO | Decision maker |
| Daniel Kerr | `daniel.kerr.ardmore-1@example.test` | Investment analyst | Architect, data engineer |
| Grace Ward | `grace.ward.ardmore-1@example.test` | Operations / finance | Ops manager |
| Harvey Rowley | `harvey.rowley.ardmore-1@example.test` | Tax adviser | Reader |
| Aaron Lyle | `aaron.lyle.ardmore-1@example.test` | External adviser | Reader (approved reports) |
| Katie Kingsley | `katie.kingsley.ardmore-1@example.test` | Family member | Reader |

To run the demo again from nothing: `python tools/reset_v1.py ardmore-1` (keeps the 186 landing files and 24 documents, removes the journey). The journey I walked on 8 October is still there if you prefer to show a finished one.

## The story in one line

A principal with domain knowledge and no data team says one sentence; by the end of the hour the office has a signed intent of work, a catalogue of every file and document it holds, a three-layer design, an honest scan of what the files can answer, a mapping sheet, loaded tables, and the first figures on screen, each traceable to a run, with the gaps named rather than filled.

## Act 1. Meredith and North (PRD section 5: principal; phase 0: product definition)

1. **Home.** "What waits for you, Meredith": nothing yet. Company page (Intent Centre): who we are, the systems (custodian, two banks, market data, benchmark provider, private portal), the policies, and the 24 documents (statements, capital notices, manager letters, invoices, the investment policy, the reconciliation policy, access and retention).
2. **One line.** *I need a trusted monthly wealth and performance report for the family.*
3. **North's six needs.** Answer in your words; the sentences below are what I used:
   - *Goal:* one trusted monthly picture: net worth, performance against the benchmark blend, and whether the data reconciles; the committee decides on rebalancing and managers; the tax adviser uses lots and income; by the 8th working day.
   - *Process today:* operations downloads the custodian files and bank balances on the 3rd working day; the analyst loads prices, FX and benchmark levels, reconciles, computes returns in a spreadsheet; the principal reviews; pack to the committee by the 8th.
   - *Inputs:* custodian positions, transactions, cash, income, fees, tax lots, corporate actions; bank balances and transfers; prices and FX; the security master; benchmark levels and the blend; the target allocation; manual adjustments with approvals; the private fund portal. "All the samples are already in the landing folder."
   - *KPIs:* consolidated net worth by entity in SGD; time-weighted return monthly and since inception, net of fees; money-weighted return; return relative to the blend; allocation drift; single-issuer concentration; three-month liquidity runway; fees as a share of assets; unresolved reconciliation breaks. "The definitions are in the investment policy statement and the reconciliation policy."
   - *Rules:* who sees what (principal and committee everything; analyst and operations positions, cash and exceptions; tax adviser lots, income and fees; external adviser approved reports only); seven years; the principal approves overrides with a reason code.
   - *Unclear:* the single-issuer limit is 10 % in the policy and 12 % in the minutes; the policy stands until the committee confirms.
4. **What to show on the right.** The intent of work filling in: nine named sources, each merged with the landing folders that hold it (the custodian source carries seven folders), the catalogue of 18 landing tables with their columns and the 24 documents with what was read from each (definitions, owners, rules, with the file and a quote), fifteen KPIs (nine named, six suggested from the industry pack and marked as suggestions), six governance rules, and the unclear list. Point at the document-sourced definitions: that is the PRD's "documents, extracted facts, source references" row.
5. **Sign.** Settle the concentration point, leave the rest marked, sign. Download the Markdown. Open the room: North's hand-over to Span, Nira's "waiting on Span".

## Act 2. Daniel and Span (PRD phase 1 use cases 1 to 4; section 8 canonical model)

6. **Design.** Build → design → "Ask Span": landing, cleaned, report layers per KPI, drawn from the signed statement; Span's note names what it assumed.
7. **Scan.** "Run the scan": every KPI available, because the landing folders carry the fields. (On Neera the same screen shows "partly" and "not", with the field and file named.)
8. **Agree the scope** as Meredith: tick the nine named KPIs; leave the pack suggestions out if you want a cleaner build.
9. **Mapping sheet.** "Ask Span to draft": one row per target field; for each gold value Span names the source field and an op: sum, latest, or formula (time-weighted return, drift, runway are formulas). Download the .xlsx: this is the PRD's "ETL mapping" artefact for the engineer.

## Act 3. Daniel and Flow, then Grace (phase 1 use cases 1, 3, 6; acceptance "every value traces to source")

10. **Run the load.** Flow stages each folder (monthly files stacked under one header, so a renamed column shows as empty cells), loads bronze → silver, runs the checks, builds the sum/latest marts, and for each formula asks the model for one SELECT over the silver tables, checks it (one SELECT, only the KPI's silver tables, no file or network functions, columns period and value) and runs it. A KPI the tables cannot yield is declined with the reason; the SQL that ran is on the mapping row for Daniel to read or replace. The room shows Flow's notes, including the manual adjustments file that fails its checks (the planted approvals quirk) and the three sources the Watcher calls late.
11. **Loaded.** Grace on Build → ops: Loaded for 2026-09 per source. That opens Consume.

## Act 4. Consume (phase 1 reports; phase 2 as offers)

12. **The cards.** Figures for the KPIs Flow built, each opening to its run and rows; "Not built yet" or "Not available yet" with the reason for the rest. Say it plainly: the product never shows a number it did not compute.
13. **Offers.** "With an FX rates feed you would also get …" and the other pack feeds not yet in the statement: these are the PRD's phase 2 items (private commitments, attribution, risk, liquidity forecasting). "We have it" reopens the statement at version 2 and tells North.
14. **Map.** This intent → its problem → nine sources → fifteen KPIs → tables.

## What the demo proves against the PRD

| PRD requirement | Where it shows |
|---|---|
| Scheduled file ingestion, immutable raw inputs, every version kept | landing folders with `_manifest.json`; bronze tables; runs log |
| Normalised identifiers and classifications | security master as a source; the catalogue's fields with meanings from the documents |
| Reconciliation, exceptions (missing price, unknown security, duplicate, stale file, out of balance) | the scan, Flow's checks and notes, the Watcher's late-source alerts; the answer key says which date and amount to look for |
| TWR, MWR, benchmark comparison | KPIs K02 to K04 in the statement; built only where Flow's SQL passes its checks, otherwise an honest "not built" |
| Drill-through from a figure to source records | Consume: click a value → run → rows |
| Manual overrides with approval and reason codes | the manual adjustments workbook (sheets adjustments, approvals) as a source; its failed check in Flow's note |
| Access control by role | the seats; Harvey, Aaron and Katie read Consume only |
| Document facts with source references | every document source in the catalogue carries what was read and where |

## What 1.0 does not do (say it before someone asks)

- Daily reconciliation by account and date as a screen: the scan and Flow's checks find the planted exceptions, but there is no reconciliation report page.
- XIRR, attribution, drawdown, Sharpe: Flow declines them unless the model writes SQL that passes the checks; they are phase 2.
- Private asset NAV staleness is in the data and the documents; no screen flags it yet.
