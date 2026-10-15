ILLUSTRATIVE: invented for demonstration

# 12 - Owner answers to the module 2 questionnaire (example)

How Arjun, Sara, Tom and Lina would answer the questions Nira sends for the KPIs they own. Each answer states whether it is stated, guessed or unknown. Wei does not reply. Used in the end-to-end test. The questions are the "Sense" and "Trace" questions: Tracked today? Could we track it? Where does it come from? Type of data. When it arrives, and the SLA. Dependencies. Upstream (who supplies it). In between (who reshapes it). Downstream (who consumes it). Personal data? Sample file.

Status of the requests: Arjun answered, Sara answered, Tom answered, Lina answered, Wei opened nothing and gave no reply after three days (reminder at day 3, to the organiser at day 7, "waiting on Wei").

---

## Arjun Rao, Finance Lead (data owner)

### K01 Minimum six-month funding headroom (data owner)
- **Tracked today?** Partly, monthly, by hand. Cash and money-market are in the bank files; the six-month view is only built in the consolidation workbook for the pack. (stated)
- **Could we track it?** Yes, weekly or on each new call, if the bank file is read automatically. (stated)
- **Where does it come from?** Northgate Custody Online statement CSV (cash balances and transactions), money-market from the positions file, calls from Sara's tracker, expected calls and stress from Tom. (stated)
- **Type of data.** Structured (bank files); semi-structured (workbooks). (stated)
- **Arrives and SLA.** Statement daily by 12:00 on working days. No SLA on the calls data. (stated)
- **Dependencies.** Needs the call schedule from the managers and Tom's expected-calls input. (stated)
- **Upstream.** Northgate Custody; Sara (tracker); Tom (inputs). I download the files myself. (stated)
- **In between.** I reshape it by hand in Cash_NAV_Consolidation.xlsx: paste, convert USD to SGD with a rate I type, remove internal transfers between E01 and E02. (stated)
- **Downstream.** Wei copies values into his workbook; Mei reviews; the committee reads the pack. I do not know who else gets the workbook. (stated / unknown)
- **Personal data?** Not sure: transaction narratives sometimes name family members. Treat as personal until confirmed. (stated)
- **Sample file.** I can supply a masked NGC_Statement CSV. It stays on my machine.

### K12 Stale-valuation share and K02 Reported-value evidence coverage (data owner)
- **Tracked today?** Partly. I note valuation dates next to NAV lines but do not carry them through to a share. The pack marks private valuations older than 120 days as stale by eye. (stated)
- **Where does it come from?** Bluewater NAV report for four funds (valuation_date and valuation_basis columns). PDFs from the other managers; I type the date. (stated)
- **Type of data.** Structured for Bluewater; unstructured PDF for the rest. (stated)
- **Arrives and SLA.** Bluewater by working day 8 after month-end; it slipped to day 10 in five of the last twelve months. Manager PDFs quarterly, 30 to 60 days after quarter-end, no agreed time. (stated)
- **Dependencies.** Final quarterly values replace rolled-forward ones, so earlier numbers can change. (stated)
- **Upstream.** Bluewater Fund Services client file share; Sara files the PDFs. (stated)
- **In between.** Consolidation workbook, typed values for non-Bluewater funds. (stated)
- **Downstream.** Mei, the committee. (stated)
- **Personal data?** No.
- **Could we track it?** Yes, from the NAV report once dates are kept. (guessed)

---

## Sara Lim, Operations Manager (process owner)

### K04 Known obligations due and K05 Unfunded commitments (data and process owner)
- **Tracked today?** Yes, in Capital_Call_Tracker.xlsx, updated by hand. (stated)
- **Could we track it better?** Yes, if notices arrive in a structured way and I am not the only reader. (guessed)
- **Where does it come from?** Emails to capital-calls@example.test, mostly PDFs from the managers. (stated)
- **Type of data.** Unstructured (notice) turned into a semi-structured workbook by typing. (stated)
- **Arrives and SLA.** No fixed time. The agreements give ten business days; the median I see is about five working days left on arrival. About 34 notices a year. I log a median two working days after receipt. (stated, conflicts with the written procedure)
- **Dependencies.** Managers must send to the right address; corrected notices must be linked to the notice they replace. (stated)
- **Upstream.** Managers' investor relations or fund finance; the bank file for paid confirmation (from Arjun). (stated)
- **In between.** My tracker; I mark superseded rows by hand and compute unfunded. (stated)
- **Downstream.** Arjun copies unfunded and calls into his consolidation; Tom uses the due dates to plan funding; the pack shows them. I tell Tom by chat. (stated)
- **Personal data?** Not sure. Notices do not name individuals, but covering emails might.
- **Sample.** One recent notice (10_call_notice_example.eml style) and the tracker with amounts masked.

### K14 Documents needing review (data and process owner)
- **Tracked today?** No. I remember which notices are unclear. (stated)
- **Could we track it?** Yes, with a status column used consistently. (guessed)
- **Where does it come from?** Tracker notes; the mailbox. (stated)
- **Upstream / in between / downstream.** Managers; me; Mei sees an appendix page. (stated)

### K03 Meeting-pack preparation effort (data and process owner)
- **Tracked today?** No. Nobody logs hours. My guess is about 38 hours in total: Arjun 12, me 8, Wei 10, Mei 5, Tom 3. (guessed)
- **Could we track it?** Yes, if each person logs hours per pack; I would need Mei's agreement. (guessed)
- **Where from?** A new simple log. (unknown)
- **Downstream.** Mei. (stated)

### The manager fee list
- I thought it was the analyst's. I have a Fee terms tab in the tracker that I have not edited for about seven months. I do not know the right figures and do not own the list. (stated: no owner)

---

## Tom Ng, Treasurer (business owner)

### K01 Minimum six-month funding headroom (business owner)
- **Tracked today?** Partly: monthly, by hand, in my tab of the consolidation workbook. (stated)
- **Could we track it?** Yes, if the bank file and the call schedule are available. (stated)
- **Where does it come from?** Bank statement, call notices by email through Sara, approved distributions, operating budget, the reserve in the policy. (stated)
- **Type of data.** Structured (statement) and unstructured (notices). (stated)
- **Arrives and SLA.** Statement daily by 12:00; notices no fixed time. (stated)
- **Dependencies.** Needs the call schedule from the manager, not just notices; needs notified calls in time to fund (two working days for USD). (stated)
- **Upstream.** Arjun (bank and NAV); Sara (calls). (stated)
- **In between.** I add expected calls and the stress multiplier in a tab; Arjun builds the headroom formulas. (stated)
- **Downstream.** Mei and the committee. (stated)
- **Who else uses the workbook?** I do not know. (unknown)
- **Definition.** Cash and money-market less known obligations, less stress calls, less the SGD 5 million reserve, the lowest of six months. This matches the policy, but the approved formula is still pending review. (stated)

### K06 Stress funding requirement (business owner)
- **Tracked today?** Partly: only when I rebuild it for the pack. (stated)
- **Where does it come from?** Managers' indicative schedules (rarely updated) times 1.75 with no distributions. (stated)
- **Type.** Unstructured emails and decks turned into a spreadsheet estimate. (guessed)
- **Arrives and SLA.** None. (stated)
- **Downstream.** Funding page of the pack. (stated)

### K15 Manager performance versus benchmark and K16 Excess return versus benchmark (data and process owner)
- **Tracked today?** Partly. Monthly for public holdings, quarterly for private funds, by hand in Performance_Workbook.xlsx. (stated)
- **Could we track it?** Yes, if the index levels and prices arrive by API instead of being pasted. (guessed)
- **Where does it come from?** Two sources of index levels and prices: a market data vendor API (Bloomberg Data License, illustrative) and an index provider's service for the S&P 500 and MSCI World levels; neither is connected, I paste from a download. Fund returns from the custody positions file and Bluewater NAV, and for private funds from manager statements. The workbook itself is an Excel file. (stated)
- **Type of data.** Structured (API levels, bank and administrator files); unstructured (statement PDFs); semi-structured (Excel). (stated)
- **Arrives and SLA.** Index levels daily after market close; I do not know the vendor's SLA or whether our licence lets us use the levels in a pack. Manager statements 30 to 60 days after quarter-end, no agreed time. (stated / unknown)
- **Dependencies.** An agreed benchmark and an agreed return method per fund. Final quarterly values replace rolled-forward ones. (stated)
- **Upstream.** The vendor, the index provider, Northgate, Bluewater, the managers' emails (via Sara). (stated)
- **In between.** My Performance_Workbook.xlsx: paste, compute period return, subtract the benchmark; benchmarks picked from memory. (stated)
- **Downstream.** Mei, the committee note, and Lina by spreadsheet for the bonus round. (stated)
- **Personal data?** No. (stated)
- **Who owns the benchmark choice?** Nobody. (stated: no owner)
- **Sample file.** A masked Performance_Workbook.xlsx. It stays on my machine.

---

## Mei Tan, Head of Investments (business owner of K15, K16, K17, K19)

### K16 Excess return versus benchmark (business owner)
- **Tracked today?** Quarterly, by hand. (stated)
- **Definition.** Net of fees, time-weighted for public funds, net IRR for private funds, always against a benchmark agreed in advance. The approved method is still pending. (stated)
- **Downstream.** The committee, and the bonus and manager reviews. (stated)

---

## Lina Ho, HR Lead (business and process owner of K18)

### K18 Compensation inputs reconciled
- **Tracked today?** No. I take Finance's spreadsheet as it comes and cannot check it. (stated)
- **Could we track it?** Yes, if I can see the approved figure and the exceptions, not only a spreadsheet. (guessed)
- **Where does it come from?** An Excel spreadsheet emailed by Finance; my own Pay_Review_Workbook.xlsx. (stated)
- **Type of data.** Semi-structured, Excel. (stated)
- **Arrives and SLA.** Four to six weeks after quarter-end, no agreed time. (stated)
- **Dependencies.** The bonus policy names "performance as reported by Finance" but not which return method. (stated)
- **Upstream.** Arjun Rao (performance figure); Mei Tan (approves). (stated)
- **In between.** I apply the weights in the policy by hand. (stated)
- **Downstream.** Mei approves; payroll. (stated)
- **Personal data?** Yes: names, salary bands and bonus amounts. Only I and Mei should see it; Finance can open the folder today. (stated)
- **Sample file.** None; the workbook is personal data and will not leave my machine. A header-only copy can be offered.

---

## Wei Chen, Risk Analyst (data and process owner of K09, K10, K11; data owner of K17)

No reply. Sent three days ago; reminder after three days; the organiser (Mei) is told after seven. Offered the option to answer in a meeting instead.

Result in module 2: K09 Single-issuer concentration, K10 Private-market allocation, K11 Unhedged FX exposure and K17 Benchmark coverage of holdings show "waiting on Wei Chen". The exposure step in the process map is drawn dashed (to confirm), taken from Arjun's and Mei's accounts. Source, type, SLA, upstream and downstream for these KPIs are unknown, and are recorded as gaps for module 3.

---

## What the three answers settle, and what they leave open

Settled (stated by an owner): bank file source, SLA and type; administrator file source and timing; the tracker as the home of calls; hand steps in the consolidation; the performance workbook as the home of fund returns; the third-party API sources (vendor and index provider) for index levels; the pay workbook as personal data.
Guessed: weekly tracking is possible; hours total of 38; status column fix.
Unknown or conflicting: the vendor and index provider SLAs and the licence for using levels in a pack; who owns the benchmark choice; which return method the bonus policy means; who else receives the consolidation workbook; the call SLA (written ten business days versus about five in practice); who owns the manager fee list; everything about the exposure KPIs until Wei answers.
