ILLUSTRATIVE: invented for demonstration

# 00 - The presenter's story: Illustrative Lakeside Family Office

Everything in this folder is invented. The office, the people, the funds, the bank, the administrator, the data vendors, the systems and every amount are fictional and round. Currency amounts are illustrative. Email addresses use example.test only. Nothing here is real or refers to a real company, person, fund or account. The presenter's script runs from login to the signed baseline, then teases module 3.

## The office in one paragraph

Illustrative Lakeside Family Office (ILFO) runs the investments of one family. It is a single family office, not a multi-family office. Two entities are reported together in SGD: Lakeside Holdings Pte Ltd (code E01, the holding company) and Lakeside Investments Pte Ltd (code E02, the investment subsidiary). Included assets are about SGD 250 million (illustrative). Cash and securities sit at Northgate Custody. Four private funds are administered by Bluewater Fund Services. Seven private commitments (USD 67 million in total, USD 29 million still unfunded) plus one open-ended public fund make up the manager list. The investment committee meets monthly, on the third Thursday.

## The cast (all illustrative)

| Person | Role | Part in the story |
|---|---|---|
| Mei Tan | Head of Investments | Sponsor. Reviews the pack. Business owner of exposure, the call KPIs and performance versus benchmark. |
| Arjun Rao | Finance Lead | Data owner for the Northgate bank files, the Bluewater administrator files and the performance workbook. Builds the consolidation workbook. |
| Sara Lim | Operations Manager | Process owner. Keeps the capital-call tracker and the shared calls and manager-statement mailboxes. Assembles the pack. |
| Wei Chen | Risk Analyst | Builds the exposure workbook by hand. Does not reply to the module 2 questionnaire. |
| Tom Ng | Treasurer | Business owner of funding capacity. Arranges cash and FX to meet calls. |
| Lina Ho | HR Lead | Runs the quarterly pay review and the bonus round. Waits for a spreadsheet from Finance. Owner of the pay workbook (personal data). |

There is also a Finance Officer (Arjun's deputy for payment release) and an Investment Analyst seat that has been vacant for seven months. That vacancy is why nobody owns the manager fee list or the benchmark choices: the analyst used to keep them.

## The five problems (what module 1 finds)

In the intent workshop each person talks to North alone for fifteen minutes, then the notes land on the board and are grouped. Five clusters come out.

1. **Are our managers beating their benchmarks? (Must).** Mei wants to know whether the funds and managers are ahead of their benchmarks (an S&P 500 index for US public equity, an MSCI World index for global equity, a private-equity benchmark for the private funds), meaning positive alpha, or falling behind. Today it is assembled by hand in Excel, months late for the private funds, and benchmarks are chosen inconsistently. In the Q2 note two managers are ahead and one is behind, and five of eight holdings have no benchmark at all (13_performance_review_note.md). Pack KPIs: Manager performance versus benchmark (K15), Excess return versus benchmark (K16), Benchmark coverage of holdings (K17).
2. **Pay depends on performance nobody trusts (Should).** The investment team's bonuses and the managers' review depend on that performance. Lina waits for a spreadsheet from Finance and cannot check it. Pack KPI: Compensation inputs reconciled (K18). Support: 14_bonus_policy_extract.md.
3. **Nobody owns our data definitions, and nobody decides who sees what (Must).** Three versions of "return", nobody owns the benchmark choices (or the fee list), and personal data sits in the pay workbook that Finance can open. Pack KPI: Data definitions with a named owner (K19). Support: 15_data_governance_issues.md.
4. **Capital calls arrive too late (Must).** Notices contractually give ten business days. In practice the email reaches the shared mailbox with about five working days left, and it is logged two working days later. Treasury then has two days to fund, and USD needs T+2. The September Harborview IV call (USD 1.5 million, due 15 September) was paid on time only because Tom bought USD on the Friday. Pack KPIs: Minimum six-month funding headroom (K01), Known obligations due (K04), Unfunded commitments (K05), Stress funding requirement (K06), Documents needing review (K14).
5. **There is no single exposure view (Must).** Exposure to one name across funds, co-investments and direct holdings takes Wei about a week to build by hand, and private funds are not in the weekly report. Meridian Cold Chain Holdings (fictional) is held through three vehicles and adds up to roughly 5 per cent of included assets, which nobody saw in one place until Wei built it. Pack KPIs: Single-issuer concentration (K09), Private-market allocation (K10), Unhedged FX exposure (K11), Reported-value evidence coverage (K02), Stale-valuation share (K12).

The old third problem, the manager fee list that nobody owns (three copies that disagree on three of eight holdings), now folds into cluster 3 as "a key list with no owner". A thread runs under all five: preparing the committee pack takes an estimated 38 person-hours, none of it logged (Meeting-pack preparation effort, K03).

## The data behind them (mixed sources, none connected)

- **Excel workbooks:** the performance workbook, the pay workbook and the capital-call tracker (plus the consolidation and exposure workbooks).
- **Email:** manager quarterly statements as PDF attachments, and capital-call notices.
- **Third-party APIs:** a market data vendor API for index levels and prices (named only as the kind of vendor: Bloomberg Data License, illustrative) and an index provider for the S&P 500 and MSCI levels.
- **The custodian's daily file** (SFTP) and **the fund administrator's NAV portal.**
- No real credentials, account numbers or client data anywhere. The "how we would connect" fields describe the method only.

## Module 1: the intent workshop, step by step

1. **Login.** Mei signs in as the company admin of Illustrative Lakeside Family Office. The Illustrative tag is visible. Show the home page of module tiles.
2. **Prepare.** Mei sets the purpose ("find what stops us trusting our performance and our funding position"), 30 minutes, anonymous notes, the family-office problem library switched on. Say that the library is a suggestion only.
3. **Lobby.** Mei, Arjun, Sara, Wei, Tom and Lina join the lobby.
4. **Each person's private room with North.** Fifteen minutes each, alone with North, the industry expert. Everyone speaks in their own words. Show North offering a labelled suggestion ("Industry practice (suggestion)") and asking one question.
   - Mei: "Are our managers beating their benchmarks? I only find out in Excel, months late."
   - Arjun: "I paste the index levels by hand and I pick the benchmark from memory."
   - Lina: "I wait for a spreadsheet from Finance for the bonus round and I cannot check it."
   - Sara: "We find out about a capital call a week before it is due."
   - Wei: "Exposure by name takes a week."
   - Tom: "If the FX deal had slipped a day we would have paid interest."
   - Nobody: "The fee list? I thought someone else had it."
5. **The board.** North groups the anonymous notes into five clusters: performance versus benchmark, pay depends on trusted performance, data governance, capital calls late, exposure. One stray note ("fee reports differ by manager") folds into data governance on the day.
6. **The votes.** Each person gets a few dots. Result: capital calls, exposure, performance versus benchmark and data governance rank highest (Must); pay on trusted numbers is Should, because it improves once performance is trusted.
7. **The charter.** Show the charter with four Must and one Should, each with the decision it supports and its pack KPIs. Mei signs; the signed charter is read-only and opens module 2.

Support documents for module 1: 11_meeting_notes_cash_planning.txt (the late-notice discussion that precedes the workshop), 10_call_notice_example.eml (the evidence), 02_investment_policy.md (what the reserve rule says), 07_capital_call_procedure.md (written versus actual), 13_performance_review_note.md, 14_bonus_policy_extract.md and 15_data_governance_issues.md (the new threads).

## Module 2: the baseline, step by step

1. **KPIs.** Module 2 takes each charter problem as KPIs, using the family_office pack: K01, K04, K05, K06, K14 (calls); K02, K09 to K12 (exposure); K15 to K17 (performance versus benchmark); K18 (pay inputs); K19 (data definitions). Show that the owners are unknown to start with.
2. **Owners.** Nominate three owners per KPI (business, data, process) from 03_org_and_roles.md. Lina is the owner for K18, Mei for K15 to K17 and K19.
3. **Nira's requests by email link.** Nira, the guide, sends each owner a short email with a link to a questionnaire (no account needed, ten minutes). The questions are "Sense" and "Trace": tracked today? could we track it? where does it come from? type of data? when it arrives? dependencies? upstream, in between, downstream? personal data? sample file?
4. **The owners' answers.** Show 12_owner_answers_example.md arriving:
   - Arjun answers for the performance KPIs: the sources are an Excel workbook and two third-party APIs (market data vendor and index provider), neither connected today, plus statement PDFs.
   - Sara, Tom answer as before.
   - Lina answers for pay: Excel, personal data, nobody checks the figure.
   - Wei does not reply. K09 to K11 and K17 show "waiting on Wei" after a reminder at day 3 and a note to the organiser at day 7.
5. **The process map.** The swimlane from 04_reporting_process_today.md: lanes Bank, managers and data vendors, Finance, Operations, Risk, Treasury, Investments, HR, Committee. Manual steps are marked MANUAL, including the new monthly performance step and the quarterly bonus step. The exposure step is drawn dashed (to confirm).
6. **The catalogue with its unknowns.** Tab 1 Sources (S01 to S15) from 05_systems_and_files.md, tab 2 Tables, tab 3 Fields (06), tab 4 Extractions (10 and 07, and the manager statement in T17). Point to the unknowns: no owner for the fee list and benchmark choices (S08, S15), vendor and index provider licence and SLA unknown (S12, S13), personal data in the pay workbook (S11), the custodian SFTP drop unused (S01).
7. **The signed baseline.** Mei signs. The baseline is read-only and is the start of module 3.

## Module 3 teaser: gap analysis and connecting the sources

- **Gap analysis.** Compare the baseline with what the five problems need. Examples: no approved definition of return; no owner for benchmarks or the fee list; five of eight holdings with no benchmark; private performance a quarter late; call notices unstructured with no fixed arrival time; hours not logged; the pay workbook open to Finance.
- **Connecting the sources.** For each source the method is described, not built: a read-only mailbox connection for statements and call notices; a scheduled pull from the custodian's SFTP drop; the administrator's NAV portal as a file pull; the market data vendor API and the index provider API for index levels and prices, once the licence is confirmed; read-only access to the Excel workbooks in place, without opening the pay columns. Every connector goes through the egress gateway, runs under the office's own credentials held on its machines, and shows counts, not rows.
- Say clearly: module 3 proposes; the office decides and signs.

## Which document supports which beat

| Beat | Document |
|---|---|
| Before the work: what to send | 01_preread_request.md |
| Rules and limits (reserve, ranges, approvals) | 02_investment_policy.md |
| Who is who, who owns what | 03_org_and_roles.md |
| The step-by-step process and pain points (swimlane) | 04_reporting_process_today.md |
| Where data comes from (catalogue tabs 1, 2) | 05_systems_and_files.md |
| Field meanings and KPI links (tab 3) | 06_data_dictionary.md |
| Calls: written versus actual | 07_capital_call_procedure.md |
| Funds, vintages, fee terms | 08_manager_list.md |
| Which pack number comes from where | 09_committee_pack_contents.md |
| Evidence of late notice | 10_call_notice_example.eml |
| Workshop context | 11_meeting_notes_cash_planning.txt |
| Owner answers for the end-to-end test | 12_owner_answers_example.md |
| Managers against benchmarks (quarterly note) | 13_performance_review_note.md |
| How pay links to performance | 14_bonus_policy_extract.md |
| Governance problems in the office's words | 15_data_governance_issues.md |

## The walk-through in ten minutes

1. Show the pre-read list and say all of it stays on the client's machine.
2. Log in as Mei; run module 1 with the six seats and show a private room with North.
3. Show the board: five clusters (performance versus benchmark, pay, governance, calls, exposure).
4. Show the votes and the charter: four Must, one Should; sign it.
5. In module 2, show the KPIs with unknown owners, then nominate Mei, Arjun, Sara, Tom, Wei and Lina.
6. Show Nira's emails with links and the answers arriving, including the API and Excel sources and Lina's pay answers; show Wei's silence with a reminder.
7. Show the process map with its manual steps (the monthly performance step and the quarterly bonus step included).
8. Show the catalogue with its unknowns: these are the first gaps.
9. Sign the baseline.
10. Teaser: module 3 does the gap analysis and describes how to connect each source.

## Consistency facts (use these everywhere)

- Third Thursday committee; pack issued two working days before (C-2). Prep effort is estimated, not logged: 38 hours (Arjun 12, Sara 8, Wei 10, Mei 5, Tom 3). The monthly performance work (Arjun about 8 hours, Mei about 2) and the quarterly bonus work (Lina about 6, Arjun and Mei about 3 each) are outside the 38.
- Northgate daily statement CSV by 12:00 on working days (portal download; an SFTP drop is also offered and unused). Bluewater monthly NAV report by working day 8, slipped to working day 10 in 5 of the last 12 months.
- 34 call notices in the last 12 months; median five working days from receipt to due date; median two working days from receipt to logging (owner estimates).
- Reserve SGD 5 million. Illustrative month-end rate 1.35 SGD per USD.
- Performance: Q2 2026 note shows Marlowe (+1.5 points against an MSCI World index) and Harborview III (+3.0 points against a private-equity benchmark) ahead, Seaglass (-5.0 points) behind. Five of eight holdings have no benchmark. Manager statements arrive 30 to 60 days after quarter-end.
- Bonus: illustrative investment-team pool SGD 600 thousand; 30% public excess return, 30% private excess return, 20% funding and risk discipline, 20% judgement.
