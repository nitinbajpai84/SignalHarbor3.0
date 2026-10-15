ILLUSTRATIVE: invented for demonstration

# 05 - Systems and files inventory

Aligned with the data catalogue template: section A is tab 1 Sources, section B is tab 2 Tables. Descriptions only: no passwords, keys or real account numbers appear here. "Connection" is how a person reaches it today. Illustrative names throughout.

## A. Sources (tab 1)

| Source ID | Name | Type | Structured? | Lands or lives | Data owner | How often | Arrival or SLA | Access and connection | Personal data? | Availability |
|---|---|---|---|---|---|---|---|---|---|---|
| S01 | Northgate Custody Online | Portal (custodian bank) | Structured | Web portal; files saved to the shared finance folder | Arjun Rao | Daily, working days | By 12:00 | Manual download by Arjun and the Finance Officer, token login (no secret recorded here). No automated feed. | Not sure (account names, distribution narratives name family members) | Available now |
| S02 | Bluewater client file share | File drop (fund administrator) | Structured | Administrator's secure share; downloaded to the finance folder | Arjun Rao | Monthly | Working day 8 after month-end (slipped to day 10 in 5 of 12 months) | Manual download by Arjun, token login | No | Available now |
| S03 | Calls mailbox capital-calls@example.test | Email (shared mailbox) | Unstructured (PDF attachments and body text) | Mail server; attachments filed to the Operations folder | Sara Lim | Irregular, about 34 call notices in 12 months | No fixed time | Read by Sara about 10:00; no deputy | Not sure | Available now |
| S04 | Manager reports folder | Shared folder (documents) | Unstructured (PDF) | Operations shared drive, one folder per manager | Sara Lim | Quarterly, 30 to 60 days after quarter-end | None agreed | Manual filing from email by Sara | No | Available now |
| S05 | Capital_Call_Tracker.xlsx | Manual workbook | Semi-structured | Operations shared drive | Sara Lim | Updated on each notice; reconciled monthly | Median 2 working days after receipt | Open file, one editor at a time | No | Available now |
| S06 | Cash_NAV_Consolidation.xlsx | Manual workbook | Semi-structured | Finance shared drive | Arjun Rao | Monthly | C-6 to C-5 | Open file; values copied from S01, S02, S05 | No | Available now |
| S07 | Exposure_Workbook.xlsx | Manual workbook | Semi-structured | Risk folder, Wei's machine and shared drive | Wei Chen | Monthly | C-5 to C-4 | Open file; only Wei edits | No | Available now |
| S08 | Manager fee list (three copies) | Mixed: tab in S05, columns in S07, appendix in the pack | Semi-structured | See text | none | Whenever someone edits | None | n/a | No | Exists, no owner |
| S09 | Committee pack and minutes | Document store | Unstructured (PDF, docx) | Operations shared drive | Sara Lim | Monthly | C-2 for the pack | Open folder | Not sure | Available now |
| S10 | Performance_Workbook.xlsx | Manual workbook | Semi-structured | Finance shared drive | Arjun Rao | Monthly (public); quarterly (private) | Working day 10 to 15 after month-end | Open file; values pasted from S01, S02, S12, S13 and typed from S14. How we would connect: read the workbook in place; replace the pastes later. | No | Available now |
| S11 | Pay_Review_Workbook.xlsx | Manual workbook | Semi-structured | HR folder, open to Finance | Lina Ho | Quarterly | 4 to 6 weeks after quarter-end | Open file, one editor. How we would connect: read only the performance columns; never open the pay columns. | Yes (names, salary bands, bonus amounts) | Available now |
| S12 | Market data vendor API (Bloomberg Data License, illustrative) | Third-party API | Structured | Vendor's cloud service; not connected | none | Daily (prices and index levels) | Unknown, after market close | Not used today; levels are pasted from a download. How we would connect: REST request on a schedule with a credential held by the office in a secrets store (no credential recorded here). | No | Not connected, licence not confirmed |
| S13 | Index provider (S&P 500 and MSCI index levels, illustrative) | Third-party API or file | Structured | Provider's service; not connected | none | Daily | Unknown | Not used today. How we would connect: API or SFTP drop of index files, key held by the office; licence for use inside the pack to be confirmed. | No | Not connected, licence not confirmed |
| S14 | Manager quarterly statements mailbox manager-reports@example.test | Email (shared mailbox) | Unstructured (PDF attachments) | Mail server; attachments filed to the manager reports folder (S04) | Sara Lim | Quarterly | 30 to 60 days after quarter-end | Read by Sara; no deputy. How we would connect: read the mailbox with a read-only mailbox permission and extract the statement fields. | Not sure | Available now |
| S15 | Benchmark choices (three places) | Mixed: a tab in S10, a slide of Mei's, the manager's own reports | Semi-structured | See text | none | Whenever someone edits | None | n/a | No | Exists, no owner |

Notes. S01 also supplies the month-end FX rate (typed by hand). The custodian also offers its daily file on an SFTP drop; ILFO does not use it, so Arjun still downloads from the portal. How we would connect: SFTP pull with a key pair held by the office. S02 is the administrator's NAV portal; same note: manual download today. S08 is shown as one row because the three copies describe the same thing; module 2 records it as "no owner".

## B. Tables, files and document types (tab 2)

| Item ID | Source | Kind | Name | Related KPIs | One record is | Frequency | Arrival or SLA | History | Confidence |
|---|---|---|---|---|---|---|---|---|---|
| T01 | S01 | File | NGC_Statement_YYYYMMDD.csv (cash balances) | K01 | One account and currency on one day | Daily | By 12:00 | 24 months in portal | Stated |
| T02 | S01 | File | NGC_Transactions_YYYYMMDD.csv | K01, K04 | One cash movement | Daily | By 12:00 | 24 months in portal | Stated |
| T03 | S01 | File | NGC_Positions_YYYYMMDD.csv (securities and money-market holdings) | K02, K09, K10, K11, K12 | One holding in one account on one day | Daily | By 12:00 | 24 months in portal | Guessed |
| T04 | S02 | File | BW_NAV_Report_YYYYMM.xlsx | K02, K05, K10, K12 | One fund held by one entity at one month-end | Monthly | Working day 8 | 36 months on share | Stated |
| T05 | S03 | Document type | Capital call notice (email and PDF) | K04, K05, K14 | One call for one fund, possibly replacing an earlier notice | Irregular | No fixed time | Mailbox, 5 years | Stated |
| T06 | S03 | Document type | Distribution notice (email and PDF) | K05, K14 | One distribution, recallable or not | Irregular | No fixed time | Mailbox, 5 years | Guessed |
| T07 | S04 | Document type | Manager quarterly report (PDF) | K02, K09, K12 | One fund for one quarter | Quarterly | 30 to 60 days late | Folder, 5 years | Stated |
| T08 | S05 | File | Capital_Call_Tracker.xlsx (tabs Calls, Commitments, Distributions, Fee terms) | K04, K05, K14 | One call, one commitment or one distribution per row | On notice | 2 working days after receipt | 4 years | Stated |
| T09 | S06 | File | Cash_NAV_Consolidation.xlsx | K01, K02, K06, K12 | One account or fund line for the month | Monthly | C-6 to C-5 | 24 monthly copies | Stated |
| T10 | S07 | File | Exposure_Workbook.xlsx | K09, K10, K11 | One holding or one look-through line | Monthly | C-5 to C-4 | 24 monthly copies | Guessed |
| T11 | S09 | Document type | Committee pack (PDF) | K03 | One monthly pack | Monthly | C-2 | 5 years | Stated |
| T12 | S08 | File | Manager fee list (three copies) | K05 | One fund's fee terms | Unknown | Unknown | Unknown | Unknown |
| T13 | S10 | File | Performance_Workbook.xlsx (tabs Public, Private, Benchmarks, Bridge) | K15, K16, K17 | One fund and period | Monthly and quarterly | Working day 10 to 15 | 3 years | Guessed |
| T14 | S11 | File | Pay_Review_Workbook.xlsx (tabs Bands, Bonus, Review) | K18 | One person and one review period | Quarterly | 4 to 6 weeks after quarter-end | 5 years | Stated |
| T15 | S12 | API dataset | Prices and index levels, daily close | K15, K16 | One instrument or index on one day | Daily | Unknown | Vendor-defined | Unknown |
| T16 | S13 | API dataset | S&P 500 and MSCI World index levels | K16, K17 | One index on one day | Daily | Unknown | Provider-defined | Unknown |
| T17 | S14 | Document type | Manager quarterly statement (PDF by email) | K15, K16, K02, K12 | One fund for one quarter, with net IRR and NAV | Quarterly | 30 to 60 days late | Mailbox, 5 years | Stated |
| T18 | S15 | File | Benchmark choices (three places) | K17, K19 | One fund and its benchmark | Unknown | Unknown | Unknown | Unknown |

## Connections between the sources

S01 and S02 feed S06 by manual copy. S05 feeds S06 by manual copy of unfunded totals. S06 feeds S07 by manual copy of values. S06 and S07 feed the pack (S09). S03 feeds S05 by typing. S04 feeds S07 (look-through typed from PDFs). S14 feeds S04 by filing and S10 by typing. S01, S02, S12 and S13 feed S10 by manual paste. S10 feeds S11 by email and paste. S10 feeds the committee note (13). S15 feeds S10 by memory.

## Access summary

- Arjun and the Finance Officer: S01, S02, S06.
- Sara: S03, S04, S05, S09, and the Operations folder.
- Wei: S07 and read access to S06.
- Arjun: also S10. Lina: S11 (and the spreadsheet emailed by Finance). Finance can open S11; Lina cannot open S10.
- Mei and Tom: read access to all workbooks and the pack.
- Nobody has an automated connection to any source, including the market data vendor API, the index provider and the custodian's SFTP drop. Everything starts from a person opening a file.

## What stays local

All samples stay on ILFO's machines. The catalogue describes these sources and holds no data from them.
