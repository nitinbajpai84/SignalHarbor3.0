# 100 use cases for a family office

Everything here is a suggestion (industry practice); the person decides. Synthetic Evergreen office, no real names. Machine-readable twin: `packs/family_office/1/use_cases_100.yaml`. Model card: `docs/v3/use-cases/UC01-CAPITAL-CALL.md`.

## Method on one page

1. **Start from how the office operates, not from features.** Seven domains: Invest, Hold and maintain, Cash and treasury, Report and govern, Operate and control, Family and people, Run the office.
2. **Fill a coverage matrix** of domain x the ten people x cadence (daily, weekly, monthly, quarterly, yearly, event). Every person owns 8 to 12 cards; every domain gets 11 to 18.
3. **One card per use case**, with: id, title, owner and who else, cadence and trigger, the decision it serves, the question in the person's words, the kind (answer, watch, act, process), the centre it lands in (Action, Build, Consume, Knowledge), the inputs (file kinds), the figures with a plain formula and how the answer key is computed from generated data, the action and who signs, what it reuses and what is new.
4. **Order so the office builds up.** `builds_on` lists earlier cards; `layer` is 1 for basics (cash, positions, commitments, valuations, statements) and rises as cards reuse figures. The picture table at the end shows the cumulative growth.
5. **Twelve cards are already tested** (the `role_builds.yaml` ids are kept: `uc6-liquidity`, `uc9-sop`, `uc10-pipeline`, `uc5-limits`, `morning-networth-note`, `uc3-statements-inbox`, `uc1-why-nav-moved`, `uc7-manager-diligence`, `uc2-recon-break-desk`, `uc6-uncalled`, `uc4-vs-benchmark`, `uc8-trades-vs-admin`). The other 88 are proposed.
6. **Rank the top 50 by pain.** Each card names the pain points it relieves (PP-xx from `painpoints_sample.yaml`, INT-xx from `problems.yaml`; KPIs from `kpi_tree.yaml`). A pain point weighs more the more distinct people and domains it touches across the 100 cards; a card's score is the sum of its pains' weights. The capital-call story (UC01) is pinned as 1 to 7; after that the highest score goes first, once the cards it builds on are placed. The top 50 cover all ten people (at least 2 each) and all seven domains.
7. **Signals (top 50).** Each top-50 card carries signal rows in the UC01 format: what arrives or exists -> the signal Harbor catches -> who acts and how little. Each has at least one exception row where Harbor stops something going wrong (the bank-details hold in UC01).
8. **Answer keys** are computed by the data generator from the universe (never typed by hand). New cards need the generator extended; the "needs" list at the end says what.

Fixture note: UC01 uses a Cedarpoint Ventures III commitment of 10,000,000; the earlier 10UC universe shows a smaller register. The generator must be extended to UC01's numbers for cards 1 to 7.

## Coverage matrix: domain x person (number of cards owned)

| Domain | CIO | CFO | HoD | Prin | Anlst | OpsL | FundA | Risk | HR | Clerk | Total |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Invest | 4 | . | . | . | 8 | 1 | 1 | 1 | . | . | **15** |
| Hold and maintain | 1 | . | 1 | 3 | 1 | . | 4 | 2 | . | 1 | **13** |
| Cash and treasury | . | 8 | . | 1 | . | 3 | 1 | 1 | . | 1 | **15** |
| Report and govern | 5 | . | 1 | 3 | 1 | . | 1 | 4 | . | . | **15** |
| Operate and control | . | . | 4 | . | . | 5 | 3 | . | . | 6 | **18** |
| Family and people | . | 1 | . | 4 | . | . | 2 | . | 4 | . | **11** |
| Run the office | . | 2 | 2 | . | . | 2 | . | 1 | 6 | . | **13** |
| **Total** | **10** | **11** | **8** | **11** | **10** | **11** | **12** | **9** | **10** | **8** | **100** |

People: CIO = Raj Patel (cio); CFO = Daniel Foo (cfo); HoD = Anita Rao (head_of_data); Prin = Mei Chen (principal); Anlst = Sofia Reyes (investment_analyst); OpsL = Grace Ong (ops_lead); FundA = Helen Foo (fund_accountant); Risk = Tom Hale (risk_officer); HR = Priya Nair (hr_admin); Clerk = Sam Lee (ops_clerk).

### Domain x cadence

| Domain | daily | weekly | monthly | quarterly | yearly | event | Total |
|---|---|---|---|---|---|---|---|
| Invest | 0 | 1 | 2 | 5 | 1 | 6 | 15 |
| Hold and maintain | 2 | 1 | 4 | 4 | 2 | 0 | 13 |
| Cash and treasury | 1 | 2 | 3 | 2 | 0 | 7 | 15 |
| Report and govern | 1 | 0 | 6 | 4 | 3 | 1 | 15 |
| Operate and control | 7 | 2 | 5 | 0 | 0 | 4 | 18 |
| Family and people | 0 | 1 | 3 | 3 | 2 | 2 | 11 |
| Run the office | 0 | 0 | 4 | 3 | 2 | 4 | 13 |
| **Total** | **11** | **7** | **27** | **21** | **10** | **24** | **100** |

### Kind and centre

| Kind | Action | Build | Consume | Knowledge | Total |
|---|---|---|---|---|---|
| answer | 0 | 0 | 37 | 0 | 37 |
| watch | 27 | 0 | 0 | 0 | 27 |
| act | 29 | 2 | 0 | 0 | 31 |
| process | 0 | 1 | 0 | 4 | 5 |

## First 50: the ranked test order

Cards 1 to 7 are the capital-call story (UC01): notice logged by Sam, recorded by Helen, Daniel checks cash and approves, Grace holds the changed bank details, treasury does the FX, Raj sees the new commitments. From 8 on, the order is pain score (highest first) once the cards it builds on are placed. Weights: INT-GOV=16, INT-RISK=16, INT-LIQ=15, INT-TRUST=14, INT-OPS=14, INT-DOC=13, PP-01=13, INT-DATAGOV=13, PP-04=13, INT-SCOPE=12, PP-07=12, PP-02=10, PP-08=9, INT-PAY=9, PP-05=8, INT-PERF=8, PP-03=8, PP-06=6, INT-BENCH=6 (people + domains touched).

| # | Card | Owner | Domain | Kind | Cadence | Pain relieved | Score | Builds on (#) |
|---|---|---|---|---|---|---|---|---|
| 1 | Log an incoming capital call notice | Sam Lee | Operate and control | act | event | PP-02, INT-DOC, INT-LIQ | 38 | - |
| 2 | Record a capital call against the commitment | Helen Foo | Cash and treasury | act | event | PP-02, INT-LIQ, INT-DOC | 38 | 1 |
| 3 | Can each entity meet its capital calls? | Daniel Foo | Cash and treasury | answer | daily | PP-01, PP-02, INT-LIQ | 38 | 2 |
| 4 | Check a call against cash and approve the payment | Daniel Foo | Cash and treasury | act | event | PP-02, INT-LIQ, INT-GOV | 41 | 2, 3 |
| 5 | Hold a payment when the bank details changed | Grace Ong | Cash and treasury | act | event | PP-02, INT-GOV, INT-DOC | 39 | 1, 4 |
| 6 | FX needed to pay a call in another currency | Grace Ong | Cash and treasury | act | event | PP-02, INT-LIQ | 25 | 4, 5, 3 |
| 7 | Commitment pacing: where we stand after the call | Raj Patel | Invest | answer | quarterly | INT-LIQ, PP-02 | 25 | 2, 3 |
| 8 | Weekly payment run with two approvals | Grace Ong | Cash and treasury | act | weekly | PP-01, INT-GOV, INT-LIQ | 44 | 3, 4 |
| 9 | Process map and SOP for the month-end report | Priya Nair | Run the office | process | event | INT-OPS, INT-DATAGOV, INT-GOV | 43 | - |
| 10 | Cash held at each bank against the bank limit | Tom Hale | Cash and treasury | answer | monthly | PP-01, INT-RISK, INT-SCOPE | 41 | 3 |
| 11 | A monthly pipeline and insight from the administrator and trading files | Anita Rao | Operate and control | process | monthly | PP-01, INT-TRUST, INT-DATAGOV | 40 | - |
| 12 | Allocation and limit monitoring | Tom Hale | Report and govern | watch | monthly | INT-RISK, INT-GOV, INT-TRUST | 46 | 11 |
| 13 | Securities with no asset class or identifier | Anita Rao | Hold and maintain | watch | weekly | INT-RISK, INT-TRUST, INT-DATAGOV | 43 | 11, 12 |
| 14 | A morning note on what we are worth | Mei Chen | Report and govern | answer | daily | PP-01, INT-TRUST, INT-LIQ | 42 | 11, 3 |
| 15 | Family member allowances and distributions due | Mei Chen | Family and people | act | monthly | INT-LIQ, PP-01, INT-GOV | 44 | 3, 14 |
| 16 | A source file arrives with a new or renamed column | Anita Rao | Operate and control | act | event | INT-DOC, INT-DATAGOV, INT-TRUST | 40 | 11 |
| 17 | What we owe: loans and facilities, and net worth after debt | Mei Chen | Hold and maintain | answer | monthly | INT-SCOPE, PP-01, INT-LIQ | 40 | 11, 14 |
| 18 | Which entity pays this call and from where | Daniel Foo | Cash and treasury | act | event | PP-02, INT-LIQ, PP-01 | 38 | 4, 3 |
| 19 | Manager statements: expected against received, and late | Helen Foo | Operate and control | watch | monthly | PP-05, INT-TRUST, INT-DOC | 35 | - |
| 20 | Why did the NAV move since the issued report? | Raj Patel | Report and govern | answer | monthly | PP-04, INT-TRUST, INT-PERF | 35 | 11, 19 |
| 21 | Valuations that are stale | Tom Hale | Hold and maintain | watch | monthly | INT-TRUST, INT-RISK, PP-04 | 43 | 11, 19, 20 |
| 22 | Amended statements and what they replace | Helen Foo | Operate and control | watch | event | PP-04, INT-DOC, INT-TRUST | 40 | 19, 20 |
| 23 | Does the issued report tie to the administrator | Helen Foo | Report and govern | watch | monthly | PP-04, PP-07, INT-TRUST | 39 | 20, 11 |
| 24 | Auditor sample: trace a figure to its file | Anita Rao | Report and govern | act | yearly | INT-TRUST, INT-GOV, PP-07 | 42 | 23, 11 |
| 25 | What changed at Kestrel Ridge since we last met? | Sofia Reyes | Invest | answer | event | PP-05, INT-TRUST, INT-DOC | 35 | 19, 20 |
| 26 | Manager statement against the administrator value | Helen Foo | Operate and control | watch | monthly | PP-04, PP-05, INT-TRUST | 35 | 20, 19 |
| 27 | Daily cash reconciliation and break desk | Grace Ong | Operate and control | watch | daily | PP-01, PP-06, INT-TRUST | 33 | 3 |
| 28 | Move cash between entities | Daniel Foo | Cash and treasury | act | event | INT-SCOPE, INT-LIQ, PP-01 | 40 | 18, 27 |
| 29 | Month-end close checklist | Grace Ong | Operate and control | process | monthly | PP-07, INT-OPS, PP-04 | 39 | 9, 27, 19, 26 |
| 30 | Vendors and contract renewals | Priya Nair | Run the office | watch | monthly | INT-OPS, INT-GOV | 30 | - |
| 31 | Where is the money: allocation by asset class and entity | Helen Foo | Hold and maintain | answer | monthly | INT-RISK, INT-SCOPE | 28 | 11, 12 |
| 32 | Allocation drift against the policy targets | Tom Hale | Report and govern | watch | monthly | INT-RISK, INT-GOV | 32 | 12, 31 |
| 33 | A real breach goes to the committee | Tom Hale | Report and govern | act | event | INT-RISK, INT-GOV | 32 | 12, 32 |
| 34 | Screen a new fund against the mandate | Sofia Reyes | Invest | act | event | INT-RISK, INT-LIQ | 31 | 31, 7 |
| 35 | Compare manager questionnaires | Sofia Reyes | Invest | answer | event | INT-TRUST, INT-DOC | 27 | 25, 34 |
| 36 | How much of our commitments is still uncalled? | Daniel Foo | Cash and treasury | answer | monthly | INT-LIQ, PP-02 | 25 | 2 |
| 37 | Distributions expected against received | Sam Lee | Cash and treasury | watch | event | PP-02, INT-LIQ, INT-DOC | 38 | 2, 36 |
| 38 | Private fund value roll-forward | Helen Foo | Hold and maintain | answer | quarterly | INT-PERF, INT-TRUST, PP-03 | 30 | 20, 36, 37 |
| 39 | Return of each private fund since we invested | Sofia Reyes | Invest | answer | quarterly | PP-03, INT-BENCH, INT-PERF | 22 | 38, 37, 2 |
| 40 | Investment committee memo for a new commitment | Sofia Reyes | Invest | act | event | INT-OPS, PP-07, INT-RISK | 42 | 35, 39, 12 |
| 41 | Approve a new commitment within policy | Raj Patel | Invest | act | event | INT-LIQ, INT-RISK, INT-GOV | 47 | 7, 12, 40, 3 |
| 42 | How did the portfolio do against its benchmark? | Raj Patel | Report and govern | answer | monthly | PP-03, INT-BENCH, INT-PERF | 22 | 11 |
| 43 | Liquid book gain or loss so far this month | Raj Patel | Hold and maintain | answer | daily | PP-03, INT-PERF | 16 | 11, 42 |
| 44 | Return for the year against the benchmark | Raj Patel | Report and govern | answer | quarterly | PP-03, INT-BENCH, INT-PERF | 22 | 42, 43 |
| 45 | Monthly investment report: assemble and sign | Raj Patel | Report and govern | act | monthly | PP-07, INT-OPS, INT-TRUST | 40 | 23, 44, 32, 14 |
| 46 | Where did the return come from | Sofia Reyes | Report and govern | answer | quarterly | PP-03, INT-PERF, INT-BENCH | 22 | 44 |
| 47 | Investment committee pack | Raj Patel | Report and govern | act | quarterly | PP-07, INT-OPS, INT-RISK | 42 | 45, 46, 33 |
| 48 | Update the allocation policy and its limits | Tom Hale | Report and govern | act | yearly | INT-RISK, INT-GOV, INT-DATAGOV | 45 | 12, 32, 47 |
| 49 | Fees paid to each manager | Helen Foo | Invest | answer | yearly | PP-03, INT-BENCH | 14 | 39 |
| 50 | Administrator and custodian invoices against the fee schedule | Grace Ong | Run the office | act | monthly | INT-OPS, PP-04, INT-GOV | 43 | 30, 49 |

Per person in the top 50: Raj Patel 8, Daniel Foo 5, Anita Rao 4, Mei Chen 3, Sofia Reyes 6, Grace Ong 6, Helen Foo 8, Tom Hale 6, Priya Nair 2, Sam Lee 2. Per domain: Operate and control 8, Cash and treasury 11, Invest 8, Run the office 3, Report and govern 13, Hold and maintain 6, Family and people 1.

## Pain point coverage (top 50)

Pain point -> the cards of the top 50 that relieve it (card numbers are the priority). "Pack coverage" is the pack's own label for the PP items. PP-06 and PP-08 are marked not in scope in the pack: the cards listed only check, read and explain; they do not book trades or prepare filings.

| Pain point | What it is | Pack coverage | People | Domains | Relieved by (top 50) |
|---|---|---|---|---|---|
| PP-01 | Nobody can say today's cash position across entities without a phone round | strong | 8 | 5 | 3, 8, 10, 11, 14, 15, 17, 18, 27, 28 |
| PP-02 | Capital calls arrive by email and the cash to meet them is found late | partial | 7 | 3 | 1, 2, 3, 4, 5, 6, 7, 18, 36, 37 |
| PP-03 | Returns by manager and fund are rebuilt by hand every month | strong | 5 | 3 | 38, 39, 42, 43, 44, 46, 49 |
| PP-04 | Our figures differ from the administrator's and nobody knows why | partial | 9 | 4 | 20, 21, 22, 23, 26, 29, 50 |
| PP-05 | Manager statements arrive late or not at all and nobody tracks it | strong | 5 | 3 | 19, 25, 26 |
| PP-06 | Trades and positions must be booked and reconciled every day | not_in_scope | 4 | 2 | 27 |
| PP-07 | The board pack is assembled from scattered files the night before | partial | 9 | 3 | 23, 24, 29, 40, 45, 47 |
| PP-08 | Tax filings and legal-entity compliance deadlines | not_in_scope | 6 | 3 | none |
| INT-BENCH | Are our managers beating their benchmarks? | problem template | 4 | 2 | 39, 42, 44, 46, 49 |
| INT-DATAGOV | Who owns our data definitions and who may see what? | problem template | 8 | 5 | 9, 11, 13, 16, 48 |
| INT-DOC | Which facts can we take from incoming documents? | problem template | 8 | 5 | 1, 2, 5, 16, 19, 22, 25, 35, 37 |
| INT-GOV | What may the agents read, and what must a person approve? | problem template | 10 | 6 | 4, 5, 8, 9, 12, 15, 24, 30, 32, 33, 41, 48, 50 |
| INT-LIQ | Can we take on another investment without compromising our cash needs? | problem template | 9 | 6 | 1, 2, 3, 4, 6, 7, 8, 14, 15, 17, 18, 28, 34, 36, 37, 41 |
| INT-OPS | How much effort does the investment meeting pack take? | problem template | 10 | 4 | 9, 29, 30, 40, 45, 47, 50 |
| INT-PAY | Can we pay people on numbers we trust? | problem template | 6 | 3 | none |
| INT-PERF | What changed the value of our assets? | problem template | 5 | 3 | 20, 38, 39, 42, 43, 44, 46 |
| INT-RISK | Where are we concentrated, and which exposures need review? | problem template | 10 | 6 | 10, 12, 13, 21, 31, 32, 33, 34, 40, 41, 47, 48 |
| INT-SCOPE | Which entities belong in one consolidated ownership view? | problem template | 8 | 4 | 10, 17, 28, 31 |
| INT-TRUST | Can we trust the consolidated picture? | problem template | 10 | 4 | 11, 12, 13, 14, 16, 19, 20, 21, 22, 23, 24, 25, 26, 27, 35, 38, 45 |

## Invest (15 cards)

### #7 P7 · Commitment pacing: where we stand after the call

`uc-007-pacing` · layer 4 · answer -> Consume

- **Owner:** Raj Patel (cio); with Daniel Foo, Sofia Reyes
- **Cadence and trigger:** quarterly; A call is recorded, and each quarter
- **Decision:** Whether we are on pace to deploy the private markets budget or need to commit more or slow down
- **Question:** "What's our unfunded commitment across all funds?"
- **Inputs:** commitments register xlsx, capital call notice pdf, allocation policy pdf
- **Figure Committed, called, unfunded by fund** (`commitments_by_fund`): Sum by fund of commitment, called and unfunded. Key: Cedarpoint III: 10,000,000 / 7,250,000 / 2,750,000; all funds 14.6m unfunded.
- **Figure Room to commit** (`budget_headroom`): Private markets budget in policy less commitments. Key: Budget in the policy fixture less the generator sum.
- **Action and sign-off:** CIO reads the updated commitments and decides whether to bring a new commitment to the committee. Signs: Raj Patel
- **Reuses:** recipes none; skills intent.define-figure, consume.answer-question, consume.explain-number
- **Builds on:** #2, #3
- **New (suggested):** figure:private_markets_budget, recipe:commitments_by_fund
- **Pain relieved:** INT-LIQ, PP-02; KPIs K01, K04, K05, K06
- **Signals:**
  - Call 7 recorded -> Unfunded across all funds is 14.6m; Cedarpoint 2,750,000 -> Raj Patel: see it, no work
  - Raj asks 'What is our unfunded commitment across all funds?' -> Answer in about a second with the funds and the file each comes from -> Raj Patel: see it, no work
  - **EXCEPTION** Total commitments plus the proposed new commitment exceed the private markets budget in the policy -> Flag on the pacing view with the amount over -> Raj Patel: 1 decision

### #25 P25 TESTED · What changed at Kestrel Ridge since we last met?

`uc7-manager-diligence` · layer 3 · answer -> Consume

- **Owner:** Sofia Reyes (investment_analyst); with Raj Patel
- **Cadence and trigger:** event; A manager meeting is booked
- **Decision:** What to ask the manager and what view to take to the committee
- **Question:** "What changed at Kestrel Ridge since the last meeting?"
- **Inputs:** manager statement pdf, newsletter pdf, meeting notes md, ddq pdf
- **Figure Manager timeline since the last meeting** (`manager_timeline`): Items dated after the last meeting, newest first, each with its source. Key: Existing key: 7,012,500.
- **Action and sign-off:** Analyst writes up a view for the committee. Signs: none (read only)
- **Reuses:** recipes none; skills intent.read-company-doc, data.read-pdf-fields, data.match-identity, check.against-source, consume.answer-question
- **Builds on:** #19, #20
- **New (suggested):** nothing new
- **Pain relieved:** PP-05, INT-TRUST, INT-DOC; KPIs K02, K07, K12, K14
- **Signals:**
  - A meeting with Kestrel Ridge is booked -> One page of what changed since 12 June: statements, restatements, newsletter team changes, newest first, each with source -> Sofia Reyes: see it, no work
  - New newsletter from the manager -> Team change picked out with page and quote -> Sofia Reyes: 1 click (add to the page)
  - **EXCEPTION** A restated value in a statement that disagrees with the one we hold -> Item shown at the top with both values -> Sofia Reyes: 1 decision

### #34 P34 · Screen a new fund against the mandate

`uc-034-prospect` · layer 5 · act -> Action

- **Owner:** Sofia Reyes (investment_analyst); with Raj Patel, Tom Hale
- **Cadence and trigger:** event; A new fund teaser arrives
- **Decision:** A new infrastructure fund sent a teaser. Does it fit our mandate and room to commit?
- **Question:** "Whether to take the fund to diligence"
- **Inputs:** fund teaser pdf, allocation policy pdf
- **Figure Fit against class, size, liquidity limits** (`mandate_fit`): Fund class and ticket size against policy limits and budget headroom. Key: Generator: teaser terms in generator; policy limits in fixture.
- **Action and sign-off:** Analyst proposes to go ahead; CIO decides. Signs: Raj Patel
- **Reuses:** recipes concentration; skills intent.read-company-doc, data.read-pdf-fields, action.size-impact
- **Builds on:** #31, #7
- **New (suggested):** table:deal_pipeline
- **Pain relieved:** INT-RISK, INT-LIQ; KPIs K01, K04, K05, K06, K08, K09, K10, K11
- **Signals:**
  - New fund teaser PDF arrives -> Class, size and liquidity read and compared with policy and room to commit -> Sofia Reyes: 1 decision (go to diligence or pass)
  - Teaser from a manager we already hold -> Linked to the existing fund page -> Sofia Reyes: see it, no work
  - **EXCEPTION** Ticket would push the class over its policy limit -> Flag with the amount over, before any meeting is booked -> Raj Patel: 1 decision

### #35 P35 · Compare manager questionnaires

`uc-035-ddq` · layer 6 · answer -> Consume

- **Owner:** Sofia Reyes (investment_analyst); with Tom Hale
- **Cadence and trigger:** event; A DDQ comes back
- **Decision:** How do the Cedarpoint and Kestrel questionnaires compare on team, fees and controls?
- **Question:** "Which answers differ from what the manager told us or from peers"
- **Inputs:** ddq pdf
- **Figure Answers side by side** (`ddq_compare`): Answers to the same question, matched by topic. Key: Generator: two generated DDQs with 5 planted differences.
- **Action and sign-off:** Analyst takes the differences to the meeting. Signs: none (read only)
- **Reuses:** recipes none; skills intent.read-company-doc, data.read-pdf-fields, consume.answer-question
- **Builds on:** #25, #34
- **New (suggested):** recipe:ddq_compare
- **Pain relieved:** INT-TRUST, INT-DOC; KPIs K02, K07, K12, K14
- **Signals:**
  - Second DDQ returned by a manager -> Answers matched by topic against the other managers; five differences listed -> Sofia Reyes: see it, no work
  - Fee answer differs from the term sheet -> Quoted both ways -> Sofia Reyes: 1 call to the manager
  - **EXCEPTION** An answer missing or marked 'to follow' on a control question -> Listed as an open item for the meeting -> Sofia Reyes: 1 decision

### #39 P39 · Return of each private fund since we invested

`uc-039-irr` · layer 6 · answer -> Consume

- **Owner:** Sofia Reyes (investment_analyst); with Helen Foo, Raj Patel
- **Cadence and trigger:** quarterly; Quarterly statements
- **Decision:** What have we made on each private fund since we first invested?
- **Question:** "Which funds earned their place and which to stop adding to"
- **Inputs:** manager statement pdf, capital call notice pdf
- **Figure IRR, TVPI, DPI by fund** (`fund_irr_tvpi`): IRR from dated calls, distributions, latest value; TVPI = (distributions + value) / called. Key: Generator: universe notices and values; IRR solved in code.
- **Action and sign-off:** Analyst presents to the CIO. Signs: none (read only)
- **Reuses:** recipes none; skills build.write-formula-table, consume.answer-question
- **Builds on:** #38, #37, #2
- **New (suggested):** recipe:fund_irr_tvpi
- **Pain relieved:** PP-03, INT-BENCH, INT-PERF; KPIs K13, K15, K16, K17
- **Signals:**
  - Statements and notices loaded -> IRR, TVPI and DPI by private fund since the first call -> Sofia Reyes: see it, no work
  - Quarter end -> League table of funds by IRR next to the fee drag -> Raj Patel: see it, no work
  - **EXCEPTION** A fund with a missing call or distribution in its history -> IRR shown as 'incomplete' with the missing dates -> Sofia Reyes: 1 call to Helen

### #40 P40 · Investment committee memo for a new commitment

`uc-040-icmemo` · layer 7 · act -> Action

- **Owner:** Sofia Reyes (investment_analyst); with Raj Patel, Tom Hale
- **Cadence and trigger:** event; A deal passes diligence
- **Decision:** Write up the recommendation for the committee.
- **Question:** "Whether to recommend the commitment"
- **Inputs:** ddq pdf, manager statement pdf, allocation policy pdf
- **Figure Figures cited in the memo** (`memo_support`): Each figure with source and run. Key: Generator: values from earlier cards.
- **Action and sign-off:** Analyst submits to the CIO. Signs: Raj Patel
- **Reuses:** recipes none; skills intent.read-company-doc, consume.explain-number
- **Builds on:** #35, #39, #12
- **New (suggested):** table:committee_decisions
- **Pain relieved:** INT-OPS, PP-07, INT-RISK; KPIs K03, K08, K09, K10, K11
- **Signals:**
  - A deal passes diligence -> Memo draft with each figure traced to a file, the policy fit and the cash cover -> Sofia Reyes: 1 click (send to Raj)
  - Memo cites a figure -> Source and run shown beside it -> Raj Patel: see it, no work
  - **EXCEPTION** A figure in the memo cannot be traced to a file -> Struck out of the draft with the reason -> Sofia Reyes: 1 decision

### #41 P41 · Approve a new commitment within policy

`uc-041-commitappr` · layer 8 · act -> Action

- **Owner:** Raj Patel (cio); with Tom Hale, Daniel Foo, Mei Chen
- **Cadence and trigger:** event; The committee agrees
- **Decision:** Can we commit 5 million to this fund and still meet our calls?
- **Question:** "Whether the commitment fits the budget, limits and cash"
- **Inputs:** allocation policy pdf, commitments register xlsx
- **Figure Budget, limit and cash tests** (`commit_check`): Headroom, concentration after, and 24 month cash cover after the commitment. Key: Generator: same arithmetic on generator rows.
- **Action and sign-off:** CIO and Principal sign; Finance records the commitment. Signs: Mei Chen
- **Reuses:** recipes none; skills action.size-impact, action.route-owner, check.adds-up
- **Builds on:** #7, #12, #40, #3
- **New (suggested):** nothing new
- **Pain relieved:** INT-LIQ, INT-RISK, INT-GOV; KPIs K01, K04, K05, K06, K08, K09, K10, K11
- **Signals:**
  - Committee agrees a 5 million commitment -> Budget room, single-name and class limits, and 24 month cash cover after the commitment -> Raj Patel: 1 decision
  - Principal asked to co-sign -> One page with the four tests green or red -> Mei Chen: 1 click (sign)
  - **EXCEPTION** Cash cover after the commitment falls below the ladder need -> Approval button replaced by the shortfall and the options -> Daniel Foo: 1 decision

### #49 P49 · Fees paid to each manager

`uc-049-feedrag` · layer 7 · answer -> Consume

- **Owner:** Helen Foo (fund_accountant); with Sofia Reyes, Daniel Foo
- **Cadence and trigger:** yearly; Year end
- **Decision:** How much have we paid each manager in fees and what share of the gain is that?
- **Question:** "Whether a manager earns its fees"
- **Inputs:** manager statement pdf, fee schedule pdf
- **Figure Fees as share of gain** (`fee_drag`): Management plus performance fees over gross gain, by manager. Key: Generator: universe fee schedules and statements.
- **Action and sign-off:** Fund Accountant gives the analyst the numbers. Signs: none (read only)
- **Reuses:** recipes none; skills data.read-pdf-fields, build.write-formula-table, check.adds-up
- **Builds on:** #39
- **New (suggested):** table:fee_schedules, table:fee_charges, recipe:fee_drag
- **Pain relieved:** PP-03, INT-BENCH; KPIs K15, K16, K17
- **Signals:**
  - Statements and fee schedules -> Fees as a share of gain by manager -> Helen Foo: see it, no work
  - Year end -> Fee drag next to IRR -> Sofia Reyes: see it, no work
  - **EXCEPTION** Fees charged above the schedule -> Listed with the overcharge -> Helen Foo: 1 call to the manager

### #53 Manager watchlist: late, restated or changed

`uc-053-watchlist` · layer 4 · watch -> Action

- **Owner:** Sofia Reyes (investment_analyst); with Raj Patel, Helen Foo
- **Cadence and trigger:** monthly; Month end after statements are logged
- **Decision:** Which managers to put on watch or to meet early
- **Question:** "Which managers have given us a late, restated or changed statement this quarter?"
- **Inputs:** manager statement pdf, email, newsletter pdf
- **Figure Flags per manager** (`watch_flags`): Count of late, amended and personnel-change items in the last 90 days. Key: Generator events per manager over 90 days.
- **Action and sign-off:** Analyst proposes the watch list; CIO decides. Signs: Raj Patel
- **Reuses:** recipes missing_statements, change_since_report; skills action.detect-exception, consume.answer-question
- **Builds on:** #25, #19
- **New (suggested):** recipe:watch_flags
- **Pain relieved:** PP-05, INT-TRUST, INT-BENCH; KPIs K02, K07, K12, K15, K16, K17

### #71 Distributions we expect in the next year

`uc-071-expdist` · layer 6 · answer -> Consume

- **Owner:** Sofia Reyes (investment_analyst); with Daniel Foo, Helen Foo
- **Cadence and trigger:** quarterly; Quarter start
- **Decision:** How much will the funds pay back to us over the next 12 months?
- **Question:** "How much money to expect back from the funds"
- **Inputs:** manager statement pdf, ddq pdf, capital call notice pdf
- **Figure Expected distributions** (`expected_distributions`): Fund value times manager projected payout rate, by quarter. Key: Generator: universe projected payout rates.
- **Action and sign-off:** Analyst hands it to the CFO for the forecast. Signs: none (read only)
- **Reuses:** recipes none; skills build.write-formula-table, consume.answer-question
- **Builds on:** #37, #38
- **New (suggested):** recipe:expected_distributions
- **Pain relieved:** INT-LIQ, PP-02; KPIs K01, K04, K05, K06

### #76 Manager scorecard

`uc-076-scorecard` · layer 8 · answer -> Consume

- **Owner:** Raj Patel (cio); with Sofia Reyes, Helen Foo
- **Cadence and trigger:** quarterly; Quarter end
- **Decision:** How does each manager score on return, fees, reporting and service?
- **Question:** "Which managers to keep, add to, or exit"
- **Inputs:** manager statement pdf, meeting notes md
- **Figure Manager score** (`manager_score`): Weighted score of return, fee drag, timeliness and watch flags. Key: Generator: weights fixed in the pack; inputs from earlier figures.
- **Action and sign-off:** CIO decides on the watch list and the next meeting. Signs: none (read only)
- **Reuses:** recipes missing_statements; skills consume.answer-question, consume.build-board
- **Builds on:** #39, #49, #53, #19
- **New (suggested):** recipe:manager_score
- **Pain relieved:** INT-BENCH, PP-05, INT-PAY; KPIs K15, K16, K17, K18

### #77 Pipeline of deals under review

`uc-077-deals` · layer 6 · watch -> Action

- **Owner:** Sofia Reyes (investment_analyst); with Raj Patel
- **Cadence and trigger:** weekly; Every Monday
- **Decision:** Where is each deal we are looking at, and what is stuck?
- **Question:** "Which deals to move forward or drop"
- **Inputs:** email, fund teaser pdf, meeting notes md
- **Figure Deals by stage and age** (`deal_stage`): Count and days in stage per deal. Key: Generator: universe deal table.
- **Action and sign-off:** Analyst updates; CIO decides. Signs: Raj Patel
- **Reuses:** recipes none; skills action.detect-exception, consume.answer-question
- **Builds on:** #34
- **New (suggested):** table:deal_pipeline
- **Pain relieved:** INT-OPS; KPIs K03

### #78 Redeem from a hedge fund within notice and lock-up

`uc-078-redemption` · layer 4 · act -> Action

- **Owner:** Grace Ong (ops_lead); with Raj Patel, Daniel Foo
- **Cadence and trigger:** event; The CIO decides to reduce a hedge fund
- **Decision:** We want out of part of Kestrel Macro. By when must we give notice and when do we get the cash?
- **Question:** "When the notice must be sent and the cash to expect"
- **Inputs:** manager statement pdf, ddq pdf
- **Figure Notice date and cash date** (`redemption_dates`): Dealing date less notice days; cash after settlement days. Key: Generator: terms in universe fund table.
- **Action and sign-off:** Operations drafts; CIO signs the notice. Signs: Raj Patel
- **Reuses:** recipes none; skills action.draft-message, action.route-owner
- **Builds on:** #3, #31
- **New (suggested):** table:fund_terms
- **Pain relieved:** INT-LIQ, PP-02; KPIs K01, K04, K05, K06

### #79 Rebalancing proposal

`uc-079-rebalance` · layer 5 · act -> Action

- **Owner:** Raj Patel (cio); with Tom Hale, Daniel Foo
- **Cadence and trigger:** monthly; Drift is outside the band
- **Decision:** We are over in listed equity. What do we sell to be back in range?
- **Question:** "Which holdings to sell or buy and how much"
- **Inputs:** allocation policy pdf, administrator export xlsx
- **Figure Amounts to trade to reach target** (`rebalance_trades`): Target value less current value by class. Key: Generator: universe allocation and targets.
- **Action and sign-off:** CIO approves; trading desk executes. Signs: Raj Patel
- **Reuses:** recipes none; skills action.size-impact, action.suggest-next-step, action.route-owner
- **Builds on:** #32, #31
- **New (suggested):** nothing new
- **Pain relieved:** INT-RISK, INT-GOV; KPIs K08, K09, K10, K11

### #80 Spread of private commitments by year

`uc-080-vintage` · layer 4 · answer -> Consume

- **Owner:** Tom Hale (risk_officer); with Raj Patel
- **Cadence and trigger:** quarterly; Quarter end
- **Decision:** How much have we committed in each vintage year?
- **Question:** "Whether commitments are too bunched in one year"
- **Inputs:** commitments register xlsx
- **Figure Commitments by vintage year** (`vintage_split`): Commitment amount by commitment date year. Key: Generator: universe commitment dates.
- **Action and sign-off:** Risk Officer shows the CIO. Signs: none (read only)
- **Reuses:** recipes none; skills consume.answer-question
- **Builds on:** #36, #31
- **New (suggested):** nothing new
- **Pain relieved:** INT-RISK, INT-LIQ; KPIs K01, K04, K05, K06, K08, K09, K10, K11

## Hold and maintain (13 cards)

### #13 P13 · Securities with no asset class or identifier

`uc-013-secgaps` · layer 3 · watch -> Action

- **Owner:** Anita Rao (head_of_data); with Sam Lee, Tom Hale
- **Cadence and trigger:** weekly; A new holding appears in the administrator file
- **Decision:** Which holdings have no asset class, and which have no identifier?
- **Question:** "Which instruments need a class or identifier before limits and allocation can be trusted"
- **Inputs:** security master xlsx, administrator export xlsx
- **Figure Holdings without class or identifier** (`unclassified_holdings`): Count and value of instruments with null asset class or no identifier. Key: Generator: universe has one convertible note with no class (PRC29 1,122,000).
- **Action and sign-off:** Head of Data asks the owner of the security master to complete it. Signs: none (read only)
- **Reuses:** recipes none; skills data.match-identity, action.detect-exception, action.size-impact
- **Builds on:** #11, #12
- **New (suggested):** table:instrument_identifiers_gaps
- **Pain relieved:** INT-RISK, INT-TRUST, INT-DATAGOV; KPIs K02, K07, K08, K09, K10, K11, K12, K19
- **Signals:**
  - New holding appears in the administrator file -> Holdings with no asset class or identifier, value 1,122,000 for the convertible -> Anita Rao: 1 click (ask the owner)
  - Owner supplies the class -> Allocation and limits recompute -> nobody: see it, no work
  - **EXCEPTION** Unclassified holdings above 1 percent of net worth -> Limits figure marked incomplete -> Anita Rao: 1 call

### #17 P17 · What we owe: loans and facilities, and net worth after debt

`uc-017-liab` · layer 5 · answer -> Consume

- **Owner:** Mei Chen (principal); with Daniel Foo
- **Cadence and trigger:** monthly; Month end and when a loan is drawn
- **Decision:** What do we owe, and what are we worth after it?
- **Question:** "Whether net worth after debt is what the family expects"
- **Inputs:** loan agreement pdf, bank statement xlsx
- **Figure Net worth less liabilities** (`net_worth_after_debt`): Net worth less loan balances in the same currency and date. Key: Generator: universe loans table, balances at month end.
- **Action and sign-off:** Principal notes it for the board. Signs: none (read only)
- **Reuses:** recipes net_worth; skills data.read-pdf-fields, build.write-formula-table, consume.answer-question
- **Builds on:** #11, #14
- **New (suggested):** table:credit_facilities, recipe:net_worth_after_debt
- **Pain relieved:** INT-SCOPE, PP-01, INT-LIQ; KPIs K01, K04, K05, K06
- **Signals:**
  - Loan statements and bank files -> What we owe and net worth after debt -> Mei Chen: see it, no work
  - Drawdown recorded -> Net worth after debt updates -> nobody: see it, no work
  - **EXCEPTION** Facility headroom below the covenant line -> Flag with the margin -> Daniel Foo: 1 decision

### #21 P21 · Valuations that are stale

`uc-021-stale` · layer 3 · watch -> Action

- **Owner:** Tom Hale (risk_officer); with Helen Foo, Sofia Reyes
- **Cadence and trigger:** monthly; Month-end values are loaded
- **Decision:** Which of our values are more than 90 days old?
- **Question:** "Which fund values are older than 90 days and so not safe to use in limits and reports"
- **Inputs:** manager statement pdf, administrator export xlsx
- **Figure Age of the latest value per fund** (`value_age_days`): As-of date less the latest valuation date, flagged above 90 days. Key: Generator: universe says C and D are stale at 9 Oct 2026.
- **Action and sign-off:** Risk Officer marks the value as stale in the limits and report notes. Signs: none (read only)
- **Reuses:** recipes none; skills action.detect-exception, check.explain-difference, consume.answer-question
- **Builds on:** #11, #19, #20
- **New (suggested):** recipe:value_age_days
- **Pain relieved:** INT-TRUST, INT-RISK, PP-04; KPIs K02, K07, K08, K09, K10, K11, K12
- **Signals:**
  - Month-end values -> Funds with a value older than 90 days (C and D at 9 Oct) -> Tom Hale: see it, no work
  - Fresh statement arrives -> Fund leaves the stale list -> nobody: see it, no work
  - **EXCEPTION** A limit breach that rests on a stale value -> Breach labelled 'possibly stale' -> Tom Hale: 1 decision

### #31 P31 · Where is the money: allocation by asset class and entity

`uc-031-alloc` · layer 3 · answer -> Consume

- **Owner:** Helen Foo (fund_accountant); with Tom Hale, Raj Patel
- **Cadence and trigger:** monthly; Month-end positions are loaded
- **Decision:** Whether the mix of the office is what the family intended
- **Question:** "What share of the family is in each asset class, and in each entity?"
- **Inputs:** administrator export xlsx, security master xlsx
- **Figure Allocation by asset class and entity** (`allocation_pct`): Market value by class and entity over total, same date and currency. Key: Generator: sum of universe holdings by asset class over the total.
- **Action and sign-off:** Share with the CIO and the Risk Officer. Signs: none (read only)
- **Reuses:** recipes net_worth, concentration; skills model.find-reusable, build.write-formula-table, consume.answer-question
- **Builds on:** #11, #12
- **New (suggested):** recipe:allocation
- **Pain relieved:** INT-RISK, INT-SCOPE; KPIs K08, K09, K10, K11
- **Signals:**
  - Month-end positions loaded -> Share of the family by asset class and entity, total ties to net worth -> Helen Foo: 1 click (share)
  - Entity or class with no mapping -> 'Unclassified' row with the amount -> Helen Foo: 1 call to the data owner
  - **EXCEPTION** Parts do not add up to net worth -> Figure not published, difference shown -> Helen Foo: 1 decision

### #38 P38 · Private fund value roll-forward

`uc-038-navroll` · layer 5 · answer -> Consume

- **Owner:** Helen Foo (fund_accountant); with Raj Patel
- **Cadence and trigger:** quarterly; A quarterly statement arrives
- **Decision:** Is the change in Fund C explained by the calls, distributions and the gain the manager reports?
- **Question:** "Whether the new value is explained by calls, distributions and gain"
- **Inputs:** manager statement pdf, capital call notice pdf
- **Figure Prior value + calls - distributions + gain = new value** (`nav_rollforward`): Roll-forward by fund and quarter; unexplained difference. Key: Generator: universe statement values and notices; unexplained difference is the key.
- **Action and sign-off:** Fund Accountant explains any unexplained difference to the CIO. Signs: none (read only)
- **Reuses:** recipes change_since_report; skills check.adds-up, check.explain-difference
- **Builds on:** #20, #36, #37
- **New (suggested):** recipe:nav_rollforward
- **Pain relieved:** INT-PERF, INT-TRUST, PP-03; KPIs K02, K07, K12, K13, K15
- **Signals:**
  - Quarterly statement arrives -> Prior value + calls - distributions + gain = new value for each fund -> Helen Foo: see it, no work
  - Roll-forward ties within a cent -> Green tick on the fund -> nobody: see it, no work
  - **EXCEPTION** The roll-forward leaves an unexplained difference -> Fund held back from reports with the amount -> Helen Foo: 1 call to the manager

### #43 P43 · Liquid book gain or loss so far this month

`uc-043-liquidpnl` · layer 3 · answer -> Consume

- **Owner:** Raj Patel (cio); with Sofia Reyes
- **Cadence and trigger:** daily; Each day after prices
- **Decision:** How much has the liquid book made or lost since the start of the month?
- **Question:** "Whether to act on a large move in the liquid book"
- **Inputs:** administrator export xlsx, market data csv
- **Figure Liquid book gain/loss month to date** (`liquid_pnl_mtd`): Value today less value at last month end less net trades. Key: Generator: universe daily values from month-end anchors; 2 dp.
- **Action and sign-off:** CIO notes it for the committee. Signs: none (read only)
- **Reuses:** recipes net_worth; skills build.write-formula-table, consume.answer-question
- **Builds on:** #11, #42
- **New (suggested):** recipe:liquid_pnl_mtd
- **Pain relieved:** PP-03, INT-PERF; KPIs K13, K15
- **Signals:**
  - Daily prices and positions -> Liquid book gain or loss since the start of the month -> Raj Patel: see it, no work
  - Month rolls over -> Start value resets with a link to the last close -> nobody: see it, no work
  - **EXCEPTION** A price that moved more than 10 percent in a day -> Held for review before it enters the figure -> Sam Lee: 1 click (confirm or correct)

### #55 Corporate actions and income calendar

`uc-055-corpact` · layer 2 · watch -> Action

- **Owner:** Sam Lee (ops_clerk); with Grace Ong
- **Cadence and trigger:** daily; The administrator or a notice announces a dividend, coupon or split
- **Decision:** Which dividends, coupons or splits are coming for the liquid book in the next two weeks?
- **Question:** "Which actions need a decision or a booking"
- **Inputs:** corporate action notice pdf, security master xlsx
- **Figure Actions due in 14 days** (`actions_next_14d`): Corporate actions with ex-date or pay date in the next 14 days. Key: Generator: universe schedules coupons on the three bonds.
- **Action and sign-off:** Clerk books the action, Operations Lead approves any election. Signs: Grace Ong
- **Reuses:** recipes none; skills data.read-pdf-fields, data.match-identity, action.detect-exception, action.route-owner
- **Builds on:** #11
- **New (suggested):** table:corporate_actions, recipe:actions_next_14d
- **Pain relieved:** PP-06, INT-DOC; KPIs K14

### #64 Currency exposure of the family

`uc-064-fxexp` · layer 5 · answer -> Consume

- **Owner:** Tom Hale (risk_officer); with Daniel Foo, Raj Patel
- **Cadence and trigger:** monthly; Month-end positions
- **Decision:** How much of what we own is in each currency, and how much is hedged?
- **Question:** "Whether to hedge a currency exposure"
- **Inputs:** administrator export xlsx, fx confirmation pdf, fx rate csv
- **Figure Net exposure by currency** (`currency_exposure`): Holdings by currency plus forwards (bought less sold), at WMR rate. Key: Generator: universe holdings by currency and 2 forwards.
- **Action and sign-off:** Risk Officer raises an unhedged exposure above the limit. Signs: Raj Patel
- **Reuses:** recipes net_worth; skills build.write-formula-table, action.detect-exception, consume.answer-question
- **Builds on:** #11, #14
- **New (suggested):** recipe:currency_exposure
- **Pain relieved:** INT-RISK, INT-LIQ; KPIs K01, K04, K05, K06, K08, K09, K10, K11

### #65 Real assets register

`uc-065-realassets` · layer 2 · answer -> Consume

- **Owner:** Mei Chen (principal); with Helen Foo, Priya Nair
- **Cadence and trigger:** yearly; Year end, and when an asset is bought or sold
- **Decision:** What property, art and other real assets do we hold and what is each worth?
- **Question:** "What real assets we own, their values and who holds them"
- **Inputs:** property valuation pdf, title deed pdf
- **Figure Real assets by type and holder** (`real_asset_value`): Latest appraisal per asset summed by type and entity. Key: Generator: universe real asset table: 6 assets with appraisal dates.
- **Action and sign-off:** Principal confirms the register. Signs: none (read only)
- **Reuses:** recipes net_worth; skills data.read-pdf-fields, data.match-identity, consume.answer-question
- **Builds on:** #11
- **New (suggested):** table:real_assets, recipe:real_asset_value
- **Pain relieved:** INT-SCOPE, INT-TRUST; KPIs K02, K07, K12

### #66 Appraisal due on a real asset

`uc-066-propreval` · layer 3 · act -> Action

- **Owner:** Mei Chen (principal); with Helen Foo, Priya Nair
- **Cadence and trigger:** yearly; An appraisal is more than 12 months old
- **Decision:** Which of our properties has not been appraised for more than a year?
- **Question:** "Whether to order a new appraisal"
- **Inputs:** property valuation pdf
- **Figure Age of latest appraisal** (`appraisal_age`): Today less latest appraisal date, flagged above 365 days. Key: Generator: universe appraisal dates.
- **Action and sign-off:** Fund Accountant drafts the request; Principal approves the spend. Signs: Mei Chen
- **Reuses:** recipes none; skills action.detect-exception, action.draft-message, action.route-owner
- **Builds on:** #65
- **New (suggested):** nothing new
- **Pain relieved:** INT-TRUST, INT-RISK; KPIs K02, K07, K08, K09, K10, K11, K12

### #67 Unrealised gain by lot

`uc-067-unrl` · layer 3 · answer -> Consume

- **Owner:** Helen Foo (fund_accountant); with Daniel Foo
- **Cadence and trigger:** quarterly; Quarter end
- **Decision:** What gain are we sitting on in each holding, by purchase lot?
- **Question:** "Which lots to sell for a tax or rebalance reason"
- **Inputs:** trade export csv, administrator export xlsx
- **Figure Unrealised gain by lot** (`unrealised_gain`): Market value less cost for each open lot. Key: Generator: universe trades build lots; value at quarter end.
- **Action and sign-off:** Fund Accountant gives the CFO the list. Signs: none (read only)
- **Reuses:** recipes net_worth; skills build.write-formula-table, consume.answer-question
- **Builds on:** #11, #51
- **New (suggested):** table:tax_lots, recipe:unrealised_gain
- **Pain relieved:** PP-08, INT-PERF; KPIs K13, K15

### #68 Dividend and coupon income forecast

`uc-068-incomef` · layer 3 · answer -> Consume

- **Owner:** Helen Foo (fund_accountant); with Daniel Foo, Raj Patel
- **Cadence and trigger:** quarterly; Quarter start
- **Decision:** How much income will the liquid book pay us over the next 12 months?
- **Question:** "How much income to plan for next year"
- **Inputs:** corporate action notice pdf, security master xlsx
- **Figure Income next 12 months** (`income_forecast`): Coupon rate times face for bonds plus dividend per share times quantity for equities. Key: Generator: universe coupon and dividend fields.
- **Action and sign-off:** Fund Accountant gives the CFO the forecast. Signs: none (read only)
- **Reuses:** recipes net_worth; skills build.write-formula-table, consume.answer-question
- **Builds on:** #11, #55
- **New (suggested):** recipe:income_forecast
- **Pain relieved:** INT-LIQ, PP-03; KPIs K01, K04, K05, K06

### #69 What the private funds really own

`uc-069-lookthru` · layer 4 · answer -> Consume

- **Owner:** Sofia Reyes (investment_analyst); with Raj Patel
- **Cadence and trigger:** quarterly; Quarterly statements
- **Decision:** Through all our funds, which companies do we own the most of?
- **Question:** "Whether the family is over-exposed to one company or sector through funds"
- **Inputs:** manager statement pdf, ddq pdf
- **Figure Look-through exposure by company** (`lookthrough_exposure`): Fund value times fund holding weight, summed by company. Key: Generator: universe fund holding lists.
- **Action and sign-off:** Analyst flags overlap to the CIO. Signs: none (read only)
- **Reuses:** recipes concentration; skills data.read-pdf-fields, data.match-identity, consume.answer-question
- **Builds on:** #11, #31, #19
- **New (suggested):** table:fund_holdings, recipe:lookthrough_exposure
- **Pain relieved:** INT-RISK, INT-SCOPE; KPIs K08, K09, K10, K11

## Cash and treasury (15 cards)

### #2 P2 · Record a capital call against the commitment

`uc-002-callrecord` · layer 2 · act -> Action

- **Owner:** Helen Foo (fund_accountant); with Sam Lee, Daniel Foo
- **Cadence and trigger:** event; A logged notice is handed over
- **Decision:** Whether the call is within the commitment and can be recorded as called, with uncalled falling by the same amount
- **Question:** "Does call 7 fit what we committed to Cedarpoint Ventures III, and what is left after it?"
- **Inputs:** capital call notice pdf, commitments register xlsx
- **Figure Called to date by fund** (`called_to_date`): Called before the notice + this notice. Key: Generator: 6,000,000 before call 7, 7,250,000 after.
- **Figure Unfunded after the call** (`unfunded_after_call`): Commitment less called to date. Key: Commitment 10,000,000 minus 7,250,000 = 2,750,000.
- **Figure Fee part against fund terms** (`fee_part_check`): Fee on the notice against the fee rate in the fund terms. Key: 350,000 equals the fee rate on file times the base; boolean from generator.
- **Action and sign-off:** Fund Accountant records the call; a call larger than the uncalled amount stops and goes to the CFO. Signs: Helen Foo
- **Reuses:** recipes none; skills data.match-identity, check.adds-up, action.detect-exception, action.route-owner
- **Builds on:** #1
- **New (suggested):** recipe:called_to_date, table:fund_notices
- **Pain relieved:** PP-02, INT-LIQ, INT-DOC; KPIs K01, K04, K05, K06, K14
- **Signals:**
  - Logged notice 7 for USD 1,250,000 -> Evergreen Holdings committed 10,000,000, called 6,000,000; after this call 7,250,000 called, 2,750,000 unfunded; fee part 350,000 matches the fund terms -> Helen Foo: 1 click (Record)
  - Call recorded -> Commitments figure updates and the open-notices count falls by one -> nobody: see it, no work
  - **EXCEPTION** A call larger than the unfunded amount, or a fee part off the fund terms -> Record is blocked and routed to the CFO with the difference -> Daniel Foo: 1 decision

### #3 P3 TESTED · Can each entity meet its capital calls?

`uc6-liquidity` · layer 3 · answer -> Consume

- **Owner:** Daniel Foo (cfo); with Mei Chen, Raj Patel
- **Cadence and trigger:** daily; Every morning, and when a call is recorded
- **Decision:** Whether each entity has cash for the calls due in 30 and 60 days, or needs a transfer
- **Question:** "What is our cash by entity today?"
- **Inputs:** administrator cash csv, commitments register xlsx, capital call notice pdf
- **Figure Cash by entity** (`cash_by_entity`): Cash recipe: market value of cash positions summed by entity and date. Key: Existing key: 2,305,906.48 / 1,252,492.34 (10UC / UC6 answer key).
- **Figure Calls due in 30 and 60 days** (`calls_due`): Sum of recorded call notices with due date inside the window, per entity. Key: Existing key: 905,000; generator sums notices by due date.
- **Action and sign-off:** CFO decides whether to fund from cash, move cash or ask for time. Signs: Daniel Foo
- **Reuses:** recipes cash_by_entity; skills intent.restate-ask, data.match-identity, check.against-source, action.detect-exception, consume.answer-question
- **Builds on:** #2
- **New (suggested):** nothing new
- **Pain relieved:** PP-01, PP-02, INT-LIQ; KPIs K01, K04, K05, K06
- **Signals:**
  - Daily administrator cash file and recorded calls -> Cash by entity and calls due in 30 and 60 days per entity -> Daniel Foo: see it, no work
  - Call 7 recorded, due 23 Oct -> Holdings has 1,230,000 USD against 1,250,000 due -> Daniel Foo: 1 decision (see next card)
  - **EXCEPTION** Administrator cash file missing at 10:00 -> Figure shown as stale with its date, no answer given as if fresh -> Grace Ong: 1 call to the administrator

### #4 P4 · Check a call against cash and approve the payment

`uc-004-callcheck` · layer 4 · act -> Action

- **Owner:** Daniel Foo (cfo); with Helen Foo, Grace Ong, Mei Chen
- **Cadence and trigger:** event; A call is recorded and falls due within 30 days
- **Decision:** Approve the payment of the call from the entity cash, or refuse and ask for a transfer
- **Question:** "Can Holdings pay the Cedarpoint call on the 23rd?"
- **Inputs:** capital call notice pdf, commitments register xlsx, administrator cash csv
- **Figure Cash after calls due, by entity** (`cash_after_calls`): Cash by entity (per currency at the planning rate) less calls due by the due date less the 250,000 buffer from the signed office rule; negative means short. Key: Holdings USD 1,230,000 vs call 1,250,000 + buffer 250,000: short USD 270,000.
- **Figure SGD to convert to cover the shortfall** (`sgd_to_convert`): Shortfall x USD/SGD WMR 4pm. Key: 270,000 x 1.3400 = 361,800.
- **Figure Notice against commitment** (`call_vs_commitment_check`): Notice amount <= unfunded before the call. Key: Boolean from generator rows.
- **Action and sign-off:** CFO approves the payment instruction; a short entity routes to the transfer or FX step. Signs: Daniel Foo
- **Reuses:** recipes cash_by_entity; skills check.against-source, action.size-impact, action.suggest-next-step, action.route-owner
- **Builds on:** #2, #3
- **New (suggested):** table:payments, recipe:cash_after_calls, table:office_rules
- **Pain relieved:** PP-02, INT-LIQ, INT-GOV; KPIs K01, K04, K05, K06
- **Signals:**
  - Daniel asks 'Can Holdings pay the Cedarpoint call on the 23rd?' -> Short USD 270,000 after the 250,000 buffer; convert about SGD 361,800 at 1.3400; each number has its source -> Daniel Foo: 1 decision (Approve, Change or Fund from another entity)
  - Approval over 500,000 USD -> The signed office rule asks for Daniel's name and time on the record -> Daniel Foo: 1 click
  - **EXCEPTION** The buffer rule would be broken by paying from the proposed source -> Harbor shows the breach and does not propose that source -> Daniel Foo: 1 decision

### #5 P5 · Hold a payment when the bank details changed

`uc-005-benefcheck` · layer 5 · act -> Action

- **Owner:** Grace Ong (ops_lead); with Sam Lee, Daniel Foo
- **Cadence and trigger:** event; A payment instruction is prepared and the wire account differs from the standing instructions
- **Decision:** Whether the changed bank details are genuine before any money moves
- **Question:** "Cedarpoint now says to wire to an account ending 4471. Is that really them?"
- **Inputs:** capital call notice pdf, email, standing instructions record
- **Figure Bank details changed against standing instructions** (`bank_details_changed`): Account on the notice versus the standing instruction on file; yes/no with old and new ending. Key: Notice account ending 4471 vs 2209 on file: yes (generator).
- **Figure Payments on hold awaiting call-back** (`payments_on_hold`): Payments to a changed account with no call-back recorded. Key: 1 until the call-back note is recorded.
- **Action and sign-off:** Grace calls a known number from the April subscription pack, records the call-back, and the standing instructions update with history. Signs: Grace Ong
- **Reuses:** recipes none; skills action.detect-exception, action.route-owner, action.close-with-reason
- **Builds on:** #1, #4
- **New (suggested):** table:standing_instructions, recipe:bank_details_changed
- **Pain relieved:** PP-02, INT-GOV, INT-DOC; KPIs K04, K05, K14
- **Signals:**
  - Payment instruction prepared for the notice -> Wire account ends 4471; standing instructions on file end 2209 -> nobody yet: Harbor holds the payment
  - **EXCEPTION** Changed bank details on a call notice -> Payment held; no suggestion to pay the new account; office rule: call back on a known number -> Grace Ong: 1 call (known number from the April subscription pack)
  - Call-back recorded -> Standing instructions update, old ones kept in history, hold released -> Grace Ong: 1 click

### #6 P6 · FX needed to pay a call in another currency

`uc-006-fxneed` · layer 6 · act -> Action

- **Owner:** Grace Ong (ops_lead); with Daniel Foo, Sam Lee
- **Cadence and trigger:** event; Thursday: the approved plan converts SGD to USD
- **Decision:** How much to convert and at what rate, and whether to book a spot or a forward
- **Question:** "We hold SGD and need USD for the call. How much do we convert, and did the bank trade at the right rate?"
- **Inputs:** fx rate csv, administrator cash csv, fx confirmation pdf
- **Figure FX confirmation against approved conversion** (`fx_plan_match`): Confirmed amount and rate against the plan, within 0.1 percent. Key: Plan SGD 361,800 at 1.3400; confirmation 1.3405, SGD 361,935 = within 0.1 percent.
- **Figure Call 7 status after the bank statement** (`call_paid_match`): Statement line matches amount and date. Key: Paid when a USD 1,250,000 debit on 23 Oct is found.
- **Action and sign-off:** Treasury books the conversion after the CFO signs; confirmation is later checked by the Clerk. Signs: Daniel Foo
- **Reuses:** recipes none; skills data.recognise-file, check.against-source, action.size-impact, action.draft-message
- **Builds on:** #4, #5, #3
- **New (suggested):** recipe:fx_required, table:bank_accounts
- **Pain relieved:** PP-02, INT-LIQ; KPIs K01, K04, K05, K06
- **Signals:**
  - Approved plan: convert SGD to USD on Thursday -> Trade to be booked for about SGD 361,800 at the planning rate -> Daniel Foo: 1 click (release the trade)
  - FX confirmation PDF arrives -> Rate 1.3405, SGD 361,935, within 0.1 percent of the plan: green -> nobody: see it, no work
  - **EXCEPTION** Confirmation differs from the plan by more than 0.1 percent -> Match goes red with the difference in SGD -> Grace Ong: 1 call to the bank

### #8 P8 · Weekly payment run with two approvals

`uc-008-payrun` · layer 5 · act -> Action

- **Owner:** Grace Ong (ops_lead); with Daniel Foo, Sam Lee
- **Cadence and trigger:** weekly; Every Thursday
- **Decision:** Which invoices and calls are ready to pay, and who has approved them?
- **Question:** "Which payments to release"
- **Inputs:** invoice pdf, capital call notice pdf
- **Figure Payments ready, approved, waiting** (`payment_batch`): Payments grouped by approval state, with total. Key: Generator: universe payments table with 3 approval states.
- **Action and sign-off:** Two people approve; Operations releases at the bank. Signs: Daniel Foo
- **Reuses:** recipes cash_by_entity; skills action.route-owner, action.close-with-reason
- **Builds on:** #3, #4
- **New (suggested):** table:payments, recipe:payment_batch
- **Pain relieved:** PP-01, INT-GOV, INT-LIQ; KPIs K01, K04, K05, K06
- **Signals:**
  - Thursday -> Payments ready, approved, and waiting, with total -> Grace Ong: 1 click (prepare)
  - Second approval given -> Moves to ready to release -> Daniel Foo: 1 click (release)
  - **EXCEPTION** A payment to an account changed since the last payment -> Held until the call-back is recorded -> Grace Ong: 1 call

### #10 P10 · Cash held at each bank against the bank limit

`uc-010-bankexp` · layer 4 · answer -> Consume

- **Owner:** Tom Hale (risk_officer); with Daniel Foo
- **Cadence and trigger:** monthly; Month-end and when an account is opened
- **Decision:** How much cash do we have at each bank, and is any over its limit?
- **Question:** "Whether too much cash sits at one bank"
- **Inputs:** bank statement xlsx, allocation policy pdf
- **Figure Cash by bank and account** (`cash_by_bank`): Closing balance per account summed by bank. Key: Generator bank statements closing balances.
- **Action and sign-off:** Risk Officer raises an over-limit bank to the CFO. Signs: none (read only)
- **Reuses:** recipes cash_by_entity; skills data.match-identity, action.detect-exception, consume.answer-question
- **Builds on:** #3
- **New (suggested):** table:bank_accounts, table:counterparties, recipe:cash_by_bank
- **Pain relieved:** PP-01, INT-RISK, INT-SCOPE; KPIs K08, K09, K10, K11
- **Signals:**
  - Month-end bank files -> Cash by bank against the bank limit -> Tom Hale: see it, no work
  - New account opened -> Appears in the table once its first statement arrives -> nobody: see it, no work
  - **EXCEPTION** Cash at one bank above its limit -> Flag with the excess -> Daniel Foo: 1 decision

### #18 P18 · Which entity pays this call and from where

`uc-018-fundplan` · layer 5 · act -> Action

- **Owner:** Daniel Foo (cfo); with Grace Ong, Mei Chen
- **Cadence and trigger:** event; A call needs funding and the paying entity is short or a better entity exists
- **Decision:** The call is 905,000. Which entity should pay it, and from which account?
- **Question:** "Which entity pays and whether a transfer is needed first"
- **Inputs:** administrator cash csv, commitments register xlsx
- **Figure Funding source per call** (`funding_plan`): Entity named in the commitment, else the entity with the most cash cover after calls. Key: call_cover for each entity from the generator.
- **Action and sign-off:** CFO approves the funding plan; Operations executes. Signs: Daniel Foo
- **Reuses:** recipes cash_by_entity; skills action.suggest-next-step, action.size-impact, action.route-owner
- **Builds on:** #4, #3
- **New (suggested):** recipe:funding_plan
- **Pain relieved:** PP-02, INT-LIQ, PP-01; KPIs K01, K04, K05, K06
- **Signals:**
  - Call recorded and falling due -> Which entity should pay and from which account -> Daniel Foo: 1 click (accept the plan)
  - Plan accepted -> Payment instruction drafted -> Grace Ong: 1 click
  - **EXCEPTION** The proposed entity ends up under the buffer -> Another entity proposed, or a transfer -> Daniel Foo: 1 decision

### #28 P28 · Move cash between entities

`uc-028-interco` · layer 6 · act -> Action

- **Owner:** Daniel Foo (cfo); with Grace Ong
- **Cadence and trigger:** event; An entity is short for a call or payment
- **Decision:** Entity B is short. Can the Trust lend it the cash, and how do we record it?
- **Question:** "Which entity lends to which, and how it is recorded"
- **Inputs:** administrator cash csv, bank statement xlsx
- **Figure Intercompany balance** (`intercompany_balance`): Transfers out less transfers in per entity pair. Key: Generator: planted loan Trust to Entity B.
- **Action and sign-off:** CFO signs the transfer; Operations executes and records it. Signs: Daniel Foo
- **Reuses:** recipes cash_by_entity; skills action.suggest-next-step, action.size-impact, action.route-owner
- **Builds on:** #18, #27
- **New (suggested):** table:intercompany, recipe:intercompany_balance
- **Pain relieved:** INT-SCOPE, INT-LIQ, PP-01; KPIs K01, K04, K05, K06
- **Signals:**
  - Entity B short for a call -> The Trust can lend the amount and stay above its buffer -> Daniel Foo: 1 click (approve)
  - Transfer made -> Intercompany balance recorded on both sides -> Grace Ong: 1 click
  - **EXCEPTION** Transfer would leave the lender under its buffer -> Not offered -> Daniel Foo: 1 decision

### #36 P36 TESTED · How much of our commitments is still uncalled?

`uc6-uncalled` · layer 3 · answer -> Consume

- **Owner:** Daniel Foo (cfo); with Mei Chen, Raj Patel
- **Cadence and trigger:** monthly; Month end and after each recorded call
- **Decision:** How much cash to plan for the year
- **Question:** "How much is uncalled across all commitments?"
- **Inputs:** commitments register xlsx
- **Figure Uncalled by fund and total** (`uncalled_total`): Commitment less called, summed. Key: Existing key: 13,450,000.
- **Action and sign-off:** CFO plans the cash for the year. Signs: none (read only)
- **Reuses:** recipes none; skills data.recognise-file, check.adds-up, consume.understand-words, consume.answer-question
- **Builds on:** #2
- **New (suggested):** nothing new
- **Pain relieved:** INT-LIQ, PP-02; KPIs K01, K04, K05, K06
- **Signals:**
  - Register and recorded calls -> Committed, called, unfunded by fund; 13,450,000 unfunded in total -> Daniel Foo: see it, no work
  - Month end -> Unfunded by year for planning -> Daniel Foo: 1 click (share with Mei)
  - **EXCEPTION** Called plus unfunded does not equal the commitment -> Fund shown in red with the difference -> Helen Foo: 1 decision

### #37 P37 · Distributions expected against received

`uc-037-distrack` · layer 4 · watch -> Action

- **Owner:** Sam Lee (ops_clerk); with Helen Foo, Daniel Foo
- **Cadence and trigger:** event; A distribution notice arrives, and weekly after its pay date
- **Decision:** Cedarpoint said it would pay a distribution on 1 September. Did it arrive?
- **Question:** "Whether money promised by a fund has arrived"
- **Inputs:** distribution notice pdf, bank statement xlsx
- **Figure Distribution notice less cash received** (`distribution_gap`): Notice amount less matching bank credit by fund and pay date. Key: Generator: notices minus bank credits; planted gap is the key.
- **Action and sign-off:** Clerk chases the manager through the Fund Accountant. Signs: Helen Foo
- **Reuses:** recipes none; skills data.read-pdf-fields, data.match-identity, action.detect-exception, action.draft-message
- **Builds on:** #2, #36
- **New (suggested):** table:fund_notices, recipe:distribution_gap
- **Pain relieved:** PP-02, INT-LIQ, INT-DOC; KPIs K01, K04, K05, K06, K14
- **Signals:**
  - Distribution notice PDF arrives -> Amount, fund and pay date read; expected bank credit set up -> Sam Lee: 1 click (Log)
  - Pay date passes -> Credit found on the bank statement and matched -> nobody: see it, no work
  - **EXCEPTION** Pay date passed and no credit found -> Gap shown with the notice amount and a chase draft -> Helen Foo: 1 click (send)

### #54 30, 60, 90 day liquidity ladder

`uc-054-ladder` · layer 5 · answer -> Consume

- **Owner:** Daniel Foo (cfo); with Mei Chen, Raj Patel
- **Cadence and trigger:** weekly; Monday, and after a recorded call
- **Decision:** Whether to raise cash, sell, or draw on a facility before the 90 day window
- **Question:** "How much cash do we have against calls and payments in the next 30, 60 and 90 days?"
- **Inputs:** administrator cash csv, capital call notice pdf, commitments register xlsx
- **Figure Cash less calls in 30, 60, 90 days** (`liquidity_ladder`): Cash by entity less calls due and approved payments within each window. Key: Generator cash and notices by due date.
- **Action and sign-off:** CFO reports the ladder to the Principal. Signs: none (read only)
- **Reuses:** recipes cash_by_entity; skills check.adds-up, consume.answer-question
- **Builds on:** #3, #4
- **New (suggested):** recipe:liquidity_ladder
- **Pain relieved:** PP-02, PP-01, INT-LIQ; KPIs K01, K04, K05, K06

### #70 Idle cash above what we need

`uc-070-idle` · layer 6 · watch -> Action

- **Owner:** Daniel Foo (cfo); with Raj Patel
- **Cadence and trigger:** monthly; Month-end cash
- **Decision:** How much cash is sitting idle above what we need for 90 days?
- **Question:** "Whether to invest, repay or hold the surplus"
- **Inputs:** administrator cash csv
- **Figure Idle cash above 90 day need** (`idle_cash`): Cash by entity less 90 day ladder outflow less buffer. Key: Generator: cash less ladder; buffer from policy.
- **Action and sign-off:** CFO proposes deployment to the CIO. Signs: Raj Patel
- **Reuses:** recipes cash_by_entity; skills action.detect-exception, action.size-impact
- **Builds on:** #3, #54
- **New (suggested):** nothing new
- **Pain relieved:** PP-01, INT-LIQ; KPIs K01, K04, K05, K06

### #72 12 month cash forecast

`uc-072-cashfc` · layer 7 · answer -> Consume

- **Owner:** Daniel Foo (cfo); with Mei Chen, Raj Patel
- **Cadence and trigger:** quarterly; Quarter start
- **Decision:** Over the next 12 months, where will cash come from and where will it go?
- **Question:** "Whether the family needs to raise cash"
- **Inputs:** commitments register xlsx, administrator cash csv
- **Figure Cash in, cash out, closing by month** (`cash_forecast`): Opening cash + distributions + income - calls - expenses. Key: Generator: sum of generator inflows and outflows by month.
- **Action and sign-off:** CFO presents to the Principal. Signs: none (read only)
- **Reuses:** recipes cash_by_entity; skills build.write-formula-table, consume.answer-question
- **Builds on:** #54, #68, #37, #71
- **New (suggested):** recipe:cash_forecast
- **Pain relieved:** INT-LIQ, PP-02, PP-01; KPIs K01, K04, K05, K06

### #73 How many months the family can spend

`uc-073-runway` · layer 6 · answer -> Consume

- **Owner:** Mei Chen (principal); with Daniel Foo
- **Cadence and trigger:** quarterly; Quarter end
- **Decision:** At our current spending, how many months of cash do we have?
- **Question:** "Whether spending is sustainable"
- **Inputs:** administrator cash csv, expense ledger xlsx
- **Figure Months of spending covered** (`cash_runway`): Liquid cash over average monthly spending of the last 6 months. Key: Generator: cash / mean expenses.
- **Action and sign-off:** Principal reviews with the CFO. Signs: none (read only)
- **Reuses:** recipes cash_by_entity; skills build.write-formula-table, consume.answer-question
- **Builds on:** #54, #15, #8
- **New (suggested):** table:office_expenses, recipe:cash_runway
- **Pain relieved:** INT-LIQ, PP-01; KPIs K01, K04, K05, K06

## Report and govern (15 cards)

### #12 P12 TESTED · Allocation and limit monitoring

`uc5-limits` · layer 2 · watch -> Action

- **Owner:** Tom Hale (risk_officer); with Raj Patel
- **Cadence and trigger:** monthly; After the September administrator export
- **Decision:** Which breaches are real and which are stale data, and what to tell the committee
- **Question:** "Which holding is over its single-name limit?"
- **Inputs:** allocation policy pdf, administrator export xlsx, security master xlsx
- **Figure Single-name concentration** (`single_name_concentration`): Concentration recipe: issuer value over portfolio total. Key: Existing key: 5.75 percent.
- **Action and sign-off:** Risk officer tells the committee about a real breach. Signs: Raj Patel
- **Reuses:** recipes concentration; skills intent.read-company-doc, build.write-formula-table, action.detect-exception, action.size-impact, check.explain-difference
- **Builds on:** #11
- **New (suggested):** nothing new
- **Pain relieved:** INT-RISK, INT-GOV, INT-TRUST; KPIs K02, K07, K08, K09, K10, K11, K12
- **Signals:**
  - Month-end administrator export and the signed allocation policy -> One holding at 5.75 percent against a 5 percent single-name limit -> Tom Hale: 1 decision (real breach or stale value)
  - Holding with no asset class -> Listed on the 'no class' list instead of being silently dropped -> Tom Hale: 1 call to the data owner
  - **EXCEPTION** A breach that rests on a value older than 90 days -> Marked 'possibly stale', not sent to the committee as real -> Tom Hale: 1 decision

### #14 P14 TESTED · A morning note on what we are worth

`morning-networth-note` · layer 4 · answer -> Consume

- **Owner:** Mei Chen (principal); with Daniel Foo, Raj Patel
- **Cadence and trigger:** daily; Each morning
- **Decision:** What needs her decision today
- **Question:** "What are we worth in the latest report?"
- **Inputs:** issued report pdf, fx rate csv
- **Figure Net worth in USD and SGD** (`networth_usd_sgd`): Report total, and total at the WMR USD/SGD rate. Key: Existing key: 57,600,000.
- **Action and sign-off:** Principal reads and decides what to tell the board of the family. Signs: none (read only)
- **Reuses:** recipes net_worth; skills intent.restate-ask, build.write-formula-table, consume.write-morning-note, consume.explain-number
- **Builds on:** #11, #3
- **New (suggested):** nothing new
- **Pain relieved:** PP-01, INT-TRUST, INT-LIQ; KPIs K01, K02, K04, K05, K06, K07, K12
- **Signals:**
  - Each morning -> What we are worth in USD and SGD, what changed, what needs her -> Mei Chen: see it, no work
  - Issued report is a month old -> Note says so with the date -> Mei Chen: see it, no work
  - **EXCEPTION** A cash call due within 7 days that the entity cannot cover -> Top line of the note, with Daniel's plan -> Mei Chen: 1 decision

### #20 P20 TESTED · Why did the NAV move since the issued report?

`uc1-why-nav-moved` · layer 2 · answer -> Consume

- **Owner:** Raj Patel (cio); with Mei Chen, Helen Foo
- **Cadence and trigger:** monthly; A manager sends an amended statement
- **Decision:** Whether a manager revision needs the committee
- **Question:** "Why did Fund A move since the issued September report?"
- **Inputs:** issued report pdf, manager statement pdf, email, administrator export xlsx
- **Figure Change since the issued report** (`change_since_report`): Amended value less the value it replaces. Key: Existing key: 10,180,000 and 180,000.
- **Action and sign-off:** CIO reads, Mei checks, revision goes to the committee if material. Signs: Mei Chen
- **Reuses:** recipes change_since_report; skills intent.restate-ask, data.read-pdf-fields, check.against-source, check.explain-difference, consume.answer-question
- **Builds on:** #11, #19
- **New (suggested):** nothing new
- **Pain relieved:** PP-04, INT-TRUST, INT-PERF; KPIs K02, K07, K12, K13, K15
- **Signals:**
  - Manager emails an amended September statement for Fund A -> Issued 10,000,000 now 10,180,000; the change 180,000 and the reason -> Raj Patel: 1 decision (does it go to the committee)
  - Amended statement filed -> Bridge from issued to known now updates -> Mei Chen: see it, no work
  - **EXCEPTION** The amended value is larger than the materiality line on the report -> Revision case opened to the CIO with the amount -> Raj Patel: 1 decision

### #23 P23 · Does the issued report tie to the administrator

`uc-023-tieout` · layer 3 · watch -> Action

- **Owner:** Helen Foo (fund_accountant); with Raj Patel, Mei Chen
- **Cadence and trigger:** monthly; Before the report is issued
- **Decision:** Whether the report can be signed
- **Question:** "Does each number on the report agree with the administrator?"
- **Inputs:** issued report xlsx, administrator export xlsx
- **Figure Report total against administrator** (`report_tie_out`): Report total less administrator total, per portfolio. Key: Generator: issued report totals less administrator totals; planted difference is the key.
- **Action and sign-off:** Fund Accountant signs the tie-out. Signs: Raj Patel
- **Reuses:** recipes net_worth, change_since_report; skills check.against-source, check.adds-up, check.explain-difference
- **Builds on:** #20, #11
- **New (suggested):** nothing new
- **Pain relieved:** PP-04, PP-07, INT-TRUST; KPIs K02, K07, K12
- **Signals:**
  - Draft monthly report -> Each portfolio total against the administrator total; ties except Fund A by 180,000 -> Helen Foo: 1 decision (explain or correct)
  - All lines tie -> Report marked ready to sign -> Raj Patel: 1 click (sign)
  - **EXCEPTION** Report total differs and the cause is not an amendment or timing -> Report held back with the unexplained amount -> Helen Foo: 1 call to the administrator

### #24 P24 · Auditor sample: trace a figure to its file

`uc-024-audit` · layer 4 · act -> Action

- **Owner:** Anita Rao (head_of_data); with Helen Foo
- **Cadence and trigger:** yearly; Auditor sends a sample request
- **Decision:** The auditor picked 12 numbers. Can we show where each came from?
- **Question:** "Whether every sampled figure traces to a source"
- **Inputs:** audit request xlsx, issued report pdf
- **Figure Share of sampled figures traced** (`trace_coverage`): Sample items with file, page and run recorded over all items. Key: Generator: sample drawn from generated report lines.
- **Action and sign-off:** Head of Data signs the trace pack for the auditor. Signs: Helen Foo
- **Reuses:** recipes none; skills consume.explain-number, check.against-source
- **Builds on:** #23, #11
- **New (suggested):** table:audit_requests
- **Pain relieved:** INT-TRUST, INT-GOV, PP-07; KPIs K02, K07, K12
- **Signals:**
  - Auditor sends a sample of 12 numbers -> Each traced to file, page, run and definition -> Anita Rao: see it, no work
  - Trace pack ready -> One page per number -> Anita Rao: 1 click (send)
  - **EXCEPTION** A sampled number with no source file -> Listed as untraced with where it was used -> Anita Rao: 1 decision

### #32 P32 · Allocation drift against the policy targets

`uc-032-driftrep` · layer 4 · watch -> Action

- **Owner:** Tom Hale (risk_officer); with Raj Patel
- **Cadence and trigger:** monthly; After month-end positions
- **Decision:** Whether drift is large enough to ask the CIO to rebalance
- **Question:** "Which asset classes are outside their policy band?"
- **Inputs:** allocation policy pdf, administrator export xlsx
- **Figure Drift from policy target** (`drift_vs_target`): Allocation percent less target percent, flagged outside the band. Key: Generator allocation less the policy target from the policy fixture.
- **Action and sign-off:** Risk Officer raises drift to the CIO. Signs: Raj Patel
- **Reuses:** recipes concentration; skills intent.read-company-doc, action.detect-exception, action.size-impact
- **Builds on:** #12, #31
- **New (suggested):** table:policy_limits
- **Pain relieved:** INT-RISK, INT-GOV; KPIs K08, K09, K10, K11
- **Signals:**
  - Month-end positions -> Listed equity at 91 percent against a 60 to 90 band -> Tom Hale: 1 click (send to Raj)
  - Back inside the band -> Item closes on its own with the date -> nobody: see it, no work
  - **EXCEPTION** Drift caused by one stale value -> Marked stale, not raised as drift -> Tom Hale: 1 decision

### #33 P33 · A real breach goes to the committee

`uc-033-breachesc` · layer 5 · act -> Action

- **Owner:** Tom Hale (risk_officer); with Raj Patel
- **Cadence and trigger:** event; A breach is confirmed real
- **Decision:** The single-name limit is breached. What is the cost to cure and who must decide?
- **Question:** "Whether to waive, cure or escalate the breach"
- **Inputs:** allocation policy pdf, administrator export xlsx
- **Figure Amount to sell to return inside the limit** (`cost_to_cure`): (exposure - limit * total) / (1 - limit). Key: Generator: universe liquid book; same formula.
- **Action and sign-off:** Risk Officer writes the note; CIO decides to cure or ask for a waiver. Signs: Raj Patel
- **Reuses:** recipes concentration; skills action.size-impact, action.suggest-next-step, action.route-owner
- **Builds on:** #12, #32
- **New (suggested):** table:committee_decisions
- **Pain relieved:** INT-RISK, INT-GOV; KPIs K08, K09, K10, K11
- **Signals:**
  - A breach confirmed real -> Cost to cure: the amount to sell to be back inside the limit -> Tom Hale: 1 click (send note)
  - Committee waives the breach -> Waiver recorded with name and date, expiry set -> Raj Patel: 1 decision
  - **EXCEPTION** Waiver past its expiry date and the breach still open -> Breach reopens in the Action list -> Tom Hale: 1 click

### #42 P42 TESTED · How did the portfolio do against its benchmark?

`uc4-vs-benchmark` · layer 2 · answer -> Consume

- **Owner:** Raj Patel (cio); with Sofia Reyes
- **Cadence and trigger:** monthly; Month-end administrator export
- **Decision:** What to tell the committee about active return
- **Question:** "How did the liquid portfolio do against the benchmark in September 2026?"
- **Inputs:** benchmark workbook xlsx, index levels csv, administrator export xlsx
- **Figure Portfolio against blended benchmark** (`active_return`): Portfolio return less blended benchmark return. Key: Existing key: 4.1667 and 2.7072.
- **Action and sign-off:** CIO puts one line in front of the committee. Signs: none (read only)
- **Reuses:** recipes none; skills intent.define-figure, build.write-formula-table, check.adds-up, consume.attribution, consume.answer-question
- **Builds on:** #11
- **New (suggested):** recipe:time_weighted_return
- **Pain relieved:** PP-03, INT-BENCH, INT-PERF; KPIs K13, K15, K16, K17
- **Signals:**
  - Month-end administrator export and index levels -> Portfolio 4.1667 against blended benchmark 2.7072 for September -> Raj Patel: see it, no work
  - Benchmark definition changed in the workbook -> Version change shown against last month -> Raj Patel: 1 decision
  - **EXCEPTION** Index level missing for a month end -> Return not computed, missing date named -> Sofia Reyes: 1 call to the data provider

### #44 P44 · Return for the year against the benchmark

`uc-044-twr` · layer 4 · answer -> Consume

- **Owner:** Raj Patel (cio); with Sofia Reyes
- **Cadence and trigger:** quarterly; Quarter end
- **Decision:** How did we do this quarter and this year against the benchmark?
- **Question:** "What to report on performance for the quarter and the year"
- **Inputs:** administrator export xlsx, index levels csv, benchmark workbook xlsx
- **Figure Time-weighted return by period** (`twr_periods`): Chain-linked monthly returns: QTD, YTD, 1y. Key: Generator: universe month-end values and cash flows; returns computed in code.
- **Action and sign-off:** CIO puts it in the committee pack. Signs: none (read only)
- **Reuses:** recipes time_weighted_return; skills build.write-formula-table, consume.attribution, consume.answer-question
- **Builds on:** #42, #43
- **New (suggested):** recipe:twr_periods
- **Pain relieved:** PP-03, INT-BENCH, INT-PERF; KPIs K13, K15, K16, K17
- **Signals:**
  - Month-end values and cash flows -> Time-weighted return for the quarter, year to date and one year against the benchmark -> Raj Patel: see it, no work
  - Large contribution mid-month -> Flow timing used so the return is not distorted -> nobody: see it, no work
  - **EXCEPTION** Monthly returns do not link to the stated quarter -> Figure held with the break -> Sofia Reyes: 1 decision

### #45 P45 · Monthly investment report: assemble and sign

`uc-045-reportpack` · layer 5 · act -> Action

- **Owner:** Raj Patel (cio); with Mei Chen, Helen Foo, Sofia Reyes
- **Cadence and trigger:** monthly; Month-end close done
- **Decision:** Is the monthly report ready to sign?
- **Question:** "Whether to sign off and issue the report"
- **Inputs:** issued report xlsx, administrator export xlsx
- **Figure Report sections ready** (`report_ready`): Share of sections with their figures traced, tied out and approved. Key: Generator: sections from the SOP; states from events.
- **Action and sign-off:** CIO signs; Principal checks; pack goes to the family. Signs: Mei Chen
- **Reuses:** recipes net_worth, change_since_report; skills consume.make-monthly-pack, check.adds-up, action.route-owner
- **Builds on:** #23, #44, #32, #14
- **New (suggested):** nothing new
- **Pain relieved:** PP-07, INT-OPS, INT-TRUST; KPIs K02, K03, K07, K12
- **Signals:**
  - Month-end close done -> Report sections drafted from traced figures: net worth, performance, drift, changes -> Raj Patel: 1 click (open)
  - Every section green -> Pack ready for the family -> Mei Chen: 1 click (check)
  - **EXCEPTION** A section based on a figure with no source -> Section withheld, the gap named -> Helen Foo: 1 decision

### #46 P46 · Where did the return come from

`uc-046-attrib` · layer 5 · answer -> Consume

- **Owner:** Sofia Reyes (investment_analyst); with Raj Patel
- **Cadence and trigger:** quarterly; Quarter end
- **Decision:** How much of the return came from asset class mix and how much from picking?
- **Question:** "Which allocation or selection decision to change"
- **Inputs:** administrator export xlsx, benchmark workbook xlsx
- **Figure Allocation and selection effect** (`attribution`): Brinson: allocation + selection + interaction = active return. Key: Generator: effects add to active return within 1 cent.
- **Action and sign-off:** Analyst presents to the CIO. Signs: none (read only)
- **Reuses:** recipes none; skills consume.attribution, check.adds-up
- **Builds on:** #44
- **New (suggested):** recipe:attribution
- **Pain relieved:** PP-03, INT-PERF, INT-BENCH; KPIs K13, K15, K16, K17
- **Signals:**
  - Quarter end -> Allocation, selection and interaction effects that add to the active return -> Sofia Reyes: see it, no work
  - Effects ready -> Slide for the committee pack -> Raj Patel: 1 click (include)
  - **EXCEPTION** Effects do not add to the active return -> Table not shown, difference named -> Sofia Reyes: 1 decision

### #47 P47 · Investment committee pack

`uc-047-icpack` · layer 6 · act -> Action

- **Owner:** Raj Patel (cio); with Tom Hale, Sofia Reyes, Mei Chen
- **Cadence and trigger:** quarterly; Committee date is set
- **Decision:** What goes in this quarter committee pack?
- **Question:** "Which matters to put to the committee and what to recommend"
- **Inputs:** issued report pdf, meeting notes md
- **Figure Pack sections and their owners** (`pack_items`): Report, performance, attribution, breaches and proposals with owner and status. Key: Generator: sections from generated events.
- **Action and sign-off:** CIO approves the pack for the committee. Signs: Raj Patel
- **Reuses:** recipes none; skills consume.make-monthly-pack, action.route-owner
- **Builds on:** #45, #46, #33
- **New (suggested):** table:committee_decisions
- **Pain relieved:** PP-07, INT-OPS, INT-RISK; KPIs K03, K08, K09, K10, K11
- **Signals:**
  - Committee date set -> Pack of report, performance, attribution, breaches and proposals with owners -> Raj Patel: 1 click (approve)
  - Section owner marks done -> Status tick -> nobody: see it, no work
  - **EXCEPTION** A section still open 2 days before the committee -> Owner named and reminded -> Raj Patel: 1 call

### #48 P48 · Update the allocation policy and its limits

`uc-048-policyupd` · layer 7 · act -> Action

- **Owner:** Tom Hale (risk_officer); with Raj Patel, Mei Chen
- **Cadence and trigger:** yearly; Annual review or a committee request
- **Decision:** Do our limits still fit, and what would the committee change?
- **Question:** "Which limits to change and by how much"
- **Inputs:** allocation policy pdf, meeting notes md
- **Figure Proposed against current limits** (`limit_changes`): Proposed minus current limit, with the number of breaches each would have caused in 12 months. Key: Generator: re-run limit check on 12 months of universe positions.
- **Action and sign-off:** Principal signs the new policy. Signs: Mei Chen
- **Reuses:** recipes concentration; skills intent.read-company-doc, action.size-impact, intent.map-decision-path
- **Builds on:** #12, #32, #47
- **New (suggested):** table:policy_limits
- **Pain relieved:** INT-RISK, INT-GOV, INT-DATAGOV; KPIs K08, K09, K10, K11, K19
- **Signals:**
  - Annual review -> Each limit with the breaches it would have caused over 12 months -> Tom Hale: 1 decision (propose)
  - Committee approves a change -> New limit version with date and signer; the limits check uses it from that date -> Mei Chen: 1 click (sign)
  - **EXCEPTION** A proposal that would leave an existing holding in breach -> Shown with the holding and amount -> Raj Patel: 1 decision

### #74 Family board pack

`uc-074-boardpack` · layer 7 · answer -> Consume

- **Owner:** Mei Chen (principal); with Raj Patel, Daniel Foo
- **Cadence and trigger:** quarterly; Board date is set
- **Decision:** What should I tell the family at the board this quarter?
- **Question:** "What to tell the board of the family"
- **Inputs:** issued report pdf, meeting notes md
- **Figure Net worth, return, liquidity, decisions** (`board_summary`): Headline figures from the report pack with their sources. Key: Generator: values from earlier cards; traces to files.
- **Action and sign-off:** Principal reviews and issues. Signs: none (read only)
- **Reuses:** recipes net_worth; skills consume.write-morning-note, consume.build-board, consume.explain-number
- **Builds on:** #45, #47, #14
- **New (suggested):** nothing new
- **Pain relieved:** PP-07, INT-OPS; KPIs K03

### #75 What happened to our worth this year

`uc-075-yearwalk` · layer 8 · answer -> Consume

- **Owner:** Mei Chen (principal); with Raj Patel, Daniel Foo
- **Cadence and trigger:** yearly; Year end
- **Decision:** Why are we worth more or less than a year ago?
- **Question:** "What to tell the family about the year"
- **Inputs:** issued report pdf, administrator export xlsx
- **Figure Net worth walk** (`networth_walk`): Opening + gains + income + contributions - spending = closing. Key: Generator: universe 12 months of values and flows; walk adds to closing.
- **Action and sign-off:** Principal presents at the annual meeting. Signs: none (read only)
- **Reuses:** recipes net_worth; skills check.adds-up, consume.explain-number, consume.answer-question
- **Builds on:** #74, #23
- **New (suggested):** recipe:networth_walk
- **Pain relieved:** PP-03, INT-PERF, PP-07; KPIs K13, K15

## Operate and control (18 cards)

### #1 P1 · Log an incoming capital call notice

`uc-001-noticelog` · layer 1 · act -> Action

- **Owner:** Sam Lee (ops_clerk); with Helen Foo, Grace Ong
- **Cadence and trigger:** event; Tuesday 09:12, an email with Capital Call Notice No. 7 for Cedarpoint Ventures III
- **Decision:** Whether the notice is complete and which fund, amount and due date it carries, so it can go to the Fund Accountant
- **Question:** "A Cedarpoint call notice just came in by email. Which fund, how much and by when?"
- **Inputs:** capital call notice pdf, email
- **Figure Call notice amount, due date, purpose, wire account** (`call_notice_amount`): Read from the PDF: investor, amount, due date, purpose split, account ending; each with page and quoted line. Key: Generator prints the notice: USD 1,250,000, due 23 Oct 2026, 900,000 investments + 350,000 fee, account ending 4471.
- **Figure Notices logged and not yet recorded** (`notices_open`): Count of notices logged with no call recorded against a commitment. Key: Generated notices minus notices marked recorded.
- **Action and sign-off:** Clerk logs the notice (fund, amount, due date, page quote) and hands it to the Fund Accountant. Signs: Grace Ong
- **Reuses:** recipes none; skills data.recognise-file, data.read-pdf-fields, data.match-identity, data.detect-duplicate, action.route-owner
- **Builds on:** nothing (a basic)
- **New (suggested):** table:fund_notices, skill:read-capital-call-notice
- **Pain relieved:** PP-02, INT-DOC, INT-LIQ; KPIs K01, K04, K05, K06, K14
- **Signals:**
  - Email with 'Cedarpoint Ventures III, Capital Call Notice No. 7' PDF -> A capital call notice of a layout seen before; investor, amount, due date, purpose and wire account read with page and quote; two checks agree -> Sam Lee: 1 click (Log)
  - Same PDF forwarded a second time by the manager -> Duplicate of notice 7, nothing new logged -> nobody: see it, no work
  - **EXCEPTION** Notice carries a different amount in the body and in the table -> Fields disagree, notice is not logged as read; both quotes shown -> Sam Lee: 1 decision (which one is right) or 1 call

### #11 P11 TESTED · A monthly pipeline and insight from the administrator and trading files

`uc10-pipeline` · layer 1 · process -> Build

- **Owner:** Anita Rao (head_of_data); with Sam Lee, Helen Foo
- **Cadence and trigger:** monthly; Administrator export and trading files arrive after month end
- **Decision:** Whether the pipeline can be trusted and put live, and what happens when a column changes
- **Question:** "What was the Evergreen Liquid portfolio worth at 30 September 2026?"
- **Inputs:** administrator export xlsx, trade export csv
- **Figure Net worth by portfolio** (`net_worth`): Net worth recipe: sum of position market values per portfolio and date. Key: Existing key: Evergreen Liquid 41,200,000 at 30 Sep 2026.
- **Action and sign-off:** Head of Data approves the pipeline design and go-live. Signs: Anita Rao
- **Reuses:** recipes net_worth; skills data.profile-file, model.find-reusable, model.design-ready-table, map.map-file, build.write-ready-sql, run.on-copy, check.adds-up, consume.build-board
- **Builds on:** nothing (a basic)
- **New (suggested):** nothing new
- **Pain relieved:** PP-01, INT-TRUST, INT-DATAGOV; KPIs K02, K07, K12, K19
- **Signals:**
  - Administrator export and trading files arrive after month end -> Files recognised, mapped to the usual tables, rows in equal rows out -> Anita Rao: 1 click (go live) the first time, none after
  - A month of data loaded -> Net worth by portfolio for 30 Sep: Evergreen Liquid 41,200,000, each figure with its trail -> everyone: see it, no work
  - **EXCEPTION** A column name in the administrator file changed -> Load is held; the new name is shown against the old -> Anita Rao: 1 decision

### #16 P16 · A source file arrives with a new or renamed column

`uc-016-schemadrift` · layer 2 · act -> Build

- **Owner:** Anita Rao (head_of_data); with Sam Lee
- **Cadence and trigger:** event; The administrator file changes a column name
- **Decision:** Whether to accept the mapping change or hold the load
- **Question:** "The administrator renamed a column. What breaks, and is the new mapping safe?"
- **Inputs:** administrator export xlsx
- **Figure Columns added, renamed or dropped** (`columns_changed`): Profile of this file less the profile of the last accepted file. Key: Generator renames one column in a copy; key = that column.
- **Action and sign-off:** Head of Data approves the new mapping before the load runs. Signs: Anita Rao
- **Reuses:** recipes none; skills data.profile-file, map.map-file, map.explain-doubt, check.adds-up
- **Builds on:** #11
- **New (suggested):** nothing new
- **Pain relieved:** INT-DOC, INT-DATAGOV, INT-TRUST; KPIs K02, K07, K12, K14, K19
- **Signals:**
  - Administrator file with a renamed column -> Old and new columns lined up; mapping proposed -> Anita Rao: 1 click (accept)
  - Mapping accepted -> Next loads use it, old files unchanged -> nobody: see it, no work
  - **EXCEPTION** The new column changes a number type or a unit -> Load held, rows not loaded -> Anita Rao: 1 decision

### #19 P19 TESTED · Manager statements: expected against received, and late

`uc3-statements-inbox` · layer 1 · watch -> Action

- **Owner:** Helen Foo (fund_accountant); with Grace Ong, Sofia Reyes
- **Cadence and trigger:** monthly; Each month end, and daily after the due date
- **Decision:** Which managers to chase and when
- **Question:** "Which statement is missing and how overdue is it?"
- **Inputs:** manager statement pdf, email
- **Figure Missing and late statements** (`missing_statements`): Missing statements recipe: expected less received by fund and month. Key: Existing key: 63 days overdue.
- **Action and sign-off:** Fund Accountant sends the chase email herself. Signs: none (read only)
- **Reuses:** recipes missing_statements; skills data.recognise-file, data.read-pdf-fields, data.match-identity, action.detect-exception, action.draft-message, consume.answer-question
- **Builds on:** nothing (a basic)
- **New (suggested):** table:expected_statements_schedule
- **Pain relieved:** PP-05, INT-TRUST, INT-DOC; KPIs K02, K07, K12, K14
- **Signals:**
  - Month end passes -> Statements expected from each manager against those received; two late, one missing 63 days -> Helen Foo: 1 click (send the chase draft)
  - A statement arrives -> Matched to the fund and month, tick on the tracker -> nobody: see it, no work
  - **EXCEPTION** A statement arrives for a fund with no expectation set -> Held as 'unknown fund' with the name seen -> Helen Foo: 1 decision

### #22 P22 · Amended statements and what they replace

`uc-022-amendlog` · layer 3 · watch -> Action

- **Owner:** Helen Foo (fund_accountant); with Sam Lee, Raj Patel
- **Cadence and trigger:** event; An amended statement arrives
- **Decision:** Which statements have been amended, and which issued report used the old number?
- **Question:** "Which earlier value is replaced and whether reports already issued need a note"
- **Inputs:** manager statement pdf, email, issued report pdf
- **Figure Amendments not yet reflected in a report** (`amendments_open`): Amended statements dated after the last issued report. Key: Generator: universe amended statements (A Sep, C Jun, H1 Jul) vs report dates.
- **Action and sign-off:** Fund Accountant flags the report note to the CIO. Signs: Raj Patel
- **Reuses:** recipes change_since_report; skills data.read-pdf-fields, data.match-identity, action.detect-exception, action.route-owner
- **Builds on:** #19, #20
- **New (suggested):** nothing new
- **Pain relieved:** PP-04, INT-DOC, INT-TRUST; KPIs K02, K07, K12, K14
- **Signals:**
  - Amended statement arrives -> The value it replaces and the issued report that used it -> Helen Foo: 1 click (note the report)
  - Log updated -> Amendment listed with old and new value -> nobody: see it, no work
  - **EXCEPTION** Amended after the report was issued to the family -> Flag with the amount -> Raj Patel: 1 decision

### #26 P26 · Manager statement against the administrator value

`uc-026-stmtadmin` · layer 3 · watch -> Action

- **Owner:** Helen Foo (fund_accountant); with Grace Ong, Raj Patel
- **Cadence and trigger:** monthly; Both the statement and the administrator value are in
- **Decision:** Does the value the administrator shows for Fund A agree with the manager statement?
- **Question:** "Whether to accept the administrator value or ask the administrator to correct it"
- **Inputs:** manager statement pdf, administrator export xlsx
- **Figure Statement value less administrator value** (`statement_vs_admin`): Latest statement value less administrator value, same fund and date. Key: Generator: universe statements vs administrator rows; planted difference is the key.
- **Action and sign-off:** Fund Accountant writes the reason and asks the administrator to correct. Signs: Grace Ong
- **Reuses:** recipes change_since_report; skills data.read-pdf-fields, check.against-source, check.explain-difference
- **Builds on:** #20, #19
- **New (suggested):** nothing new
- **Pain relieved:** PP-04, PP-05, INT-TRUST; KPIs K02, K07, K12
- **Signals:**
  - Manager statement and administrator value -> Fund value on the statement against the administrator -> Helen Foo: see it, no work
  - Difference explained by an amendment -> Closes with the link -> nobody: see it, no work
  - **EXCEPTION** Difference not explained by timing or amendment -> Query draft to the administrator -> Helen Foo: 1 click (send)

### #27 P27 TESTED · Daily cash reconciliation and break desk

`uc2-recon-break-desk` · layer 4 · watch -> Action

- **Owner:** Grace Ong (ops_lead); with Sam Lee, Daniel Foo
- **Cadence and trigger:** daily; Every morning, bank and administrator files arrive
- **Decision:** Which breaks are timing and which are errors, and which go to Finance
- **Question:** "Which entity has a cash break on 8 October and by how much?"
- **Inputs:** bank statement xlsx, administrator cash csv, trade export csv
- **Figure Cash break by entity and day** (`cash_break`): Cash break recipe: administrator change in cash less movements. Key: Existing key: 12,400 (Entity B, 8 Oct).
- **Action and sign-off:** Grace closes each break with a reason or hands it to Finance. Signs: Grace Ong
- **Reuses:** recipes cash_break, cash_by_entity; skills data.recognise-file, data.match-identity, check.against-source, action.detect-exception, check.explain-difference, action.route-owner
- **Builds on:** #3
- **New (suggested):** nothing new
- **Pain relieved:** PP-01, PP-06, INT-TRUST; KPIs K02, K07, K12
- **Signals:**
  - Bank, administrator and trading cash files -> Cash difference per entity per day; Entity B 12,400 on 8 Oct -> Grace Ong: 1 click (mark timing or error)
  - Break explained as timing -> Closes itself when the item clears -> nobody: see it, no work
  - **EXCEPTION** Break over 5,000 with no explaining item -> Open break with likely cause -> Grace Ong: 1 call to the bank

### #29 P29 · Month-end close checklist

`uc-029-closeck` · layer 5 · process -> Knowledge

- **Owner:** Grace Ong (ops_lead); with Helen Foo, Daniel Foo, Priya Nair
- **Cadence and trigger:** monthly; Last business day of the month
- **Decision:** Is everything we need for the month-end report in and checked?
- **Question:** "Whether the close is complete and the report can start"
- **Inputs:** process narrative md, exception log
- **Figure Close items done and open** (`close_items_done`): Count of checklist steps done, open, and late. Key: Generator: checklist from the SOP; steps marked by generated events.
- **Action and sign-off:** Operations Lead signs the close. Signs: Grace Ong
- **Reuses:** recipes missing_statements, cash_break; skills intent.write-sop, action.detect-exception, action.route-owner
- **Builds on:** #9, #27, #19, #26
- **New (suggested):** recipe:close_items_done
- **Pain relieved:** PP-07, INT-OPS, PP-04; KPIs K03
- **Signals:**
  - Last business day -> Checklist of close items done, open and late -> Grace Ong: 1 click (sign close)
  - All items done -> Report can start -> Raj Patel: see it, no work
  - **EXCEPTION** An item open past its due date -> Owner named and reminded -> Grace Ong: 1 call

### #51 TESTED · Trades and FX forwards against the administrator and the confirmations

`uc8-trades-vs-admin` · layer 2 · watch -> Action

- **Owner:** Sam Lee (ops_clerk); with Grace Ong
- **Cadence and trigger:** daily; Each day, after the desk file arrives
- **Decision:** Which unmatched trades to send to the Operations Lead
- **Question:** "How much does the FX forward confirmation differ from our record?"
- **Inputs:** trade export csv, fx confirmation pdf, administrator export xlsx
- **Figure FX forward confirmation variance** (`fx_confirmation_variance`): Confirmation leg less the desk trade amount. Key: Existing key: 8,100.
- **Action and sign-off:** Clerk raises a break and sends it to Grace. Signs: Grace Ong
- **Reuses:** recipes fx_confirmation_variance; skills data.recognise-file, data.read-pdf-fields, check.against-source, action.detect-exception, check.explain-difference, action.route-owner
- **Builds on:** #11
- **New (suggested):** nothing new
- **Pain relieved:** PP-06, INT-DOC; KPIs K14

### #56 Custodian positions against administrator positions

`uc-056-custrecon` · layer 3 · watch -> Action

- **Owner:** Grace Ong (ops_lead); with Sam Lee, Tom Hale
- **Cadence and trigger:** daily; Custodian and administrator files both arrive
- **Decision:** Do the custodian and the administrator agree on what we hold?
- **Question:** "Which holdings differ between the custodian and the administrator, and why"
- **Inputs:** custody statement pdf, administrator export xlsx, trade export csv
- **Figure Quantity difference per holding** (`position_break`): Administrator quantity less custodian quantity, per holding and date. Key: Generator: custodian file copied from universe with 2 planted quantity changes.
- **Action and sign-off:** Operations Lead closes with a reason or chases the custodian. Signs: Grace Ong
- **Reuses:** recipes none; skills data.recognise-file, data.match-identity, check.against-source, action.detect-exception, check.explain-difference
- **Builds on:** #11, #51
- **New (suggested):** table:custody_positions, recipe:position_break
- **Pain relieved:** PP-06, PP-04, INT-TRUST; KPIs K02, K07, K12

### #57 Prices against a second source

`uc-057-pricecheck` · layer 3 · watch -> Action

- **Owner:** Grace Ong (ops_lead); with Tom Hale, Sam Lee
- **Cadence and trigger:** daily; Daily prices arrive
- **Decision:** Which of our prices are off from the market by more than 0.5 percent?
- **Question:** "Which prices differ from a second source by more than tolerance"
- **Inputs:** market data csv, administrator export xlsx
- **Figure Price difference to second source** (`price_gap_pct`): Administrator price less second-source price over second-source price. Key: Generator: second source = universe price with 2 planted changes.
- **Action and sign-off:** Operations Lead asks the administrator to confirm. Signs: Grace Ong
- **Reuses:** recipes none; skills check.against-source, action.detect-exception, check.explain-difference
- **Builds on:** #11, #51
- **New (suggested):** table:prices_second_source, recipe:price_gap_pct
- **Pain relieved:** PP-04, INT-TRUST, PP-06; KPIs K02, K07, K12

### #58 Trades not settled on time

`uc-058-settle` · layer 3 · watch -> Action

- **Owner:** Sam Lee (ops_clerk); with Grace Ong
- **Cadence and trigger:** daily; Each day after settlement date
- **Decision:** Which trades should have settled by now and have not?
- **Question:** "Which trades failed to settle and whom to chase"
- **Inputs:** trade export csv, custody statement pdf
- **Figure Trades past settlement date with no cash** (`unsettled_trades`): Trades with settlement date before today and no matching cash movement. Key: Generator: universe trades with 2 planted fails.
- **Action and sign-off:** Clerk chases the broker and informs Operations Lead. Signs: Grace Ong
- **Reuses:** recipes none; skills action.detect-exception, action.size-impact, action.draft-message
- **Builds on:** #51
- **New (suggested):** table:settlements, recipe:unsettled_trades
- **Pain relieved:** PP-06, PP-01

### #59 Open breaks by age

`uc-059-breakage` · layer 5 · watch -> Action

- **Owner:** Grace Ong (ops_lead); with Daniel Foo, Sam Lee
- **Cadence and trigger:** weekly; Every Monday
- **Decision:** Which cash breaks are still open and how long have they been open?
- **Question:** "Which breaks are older than five days and go to Finance"
- **Inputs:** exception log
- **Figure Open breaks by age** (`break_age`): Open exceptions of type cash break, age in business days from detection. Key: Exceptions table from the generator with planted detection dates.
- **Action and sign-off:** Operations Lead hands unresolved breaks to Finance. Signs: Daniel Foo
- **Reuses:** recipes cash_break; skills action.route-owner, action.close-with-reason, consume.answer-question
- **Builds on:** #27
- **New (suggested):** nothing new
- **Pain relieved:** PP-01, PP-06, INT-OPS; KPIs K03

### #60 Documents the office could not recognise

`uc-060-docinbox` · layer 2 · watch -> Action

- **Owner:** Sam Lee (ops_clerk); with Anita Rao
- **Cadence and trigger:** daily; A file lands in the dropbox and is not recognised
- **Decision:** Which files in the dropbox did Harbor not recognise?
- **Question:** "Where each unrecognised file belongs or whether to refuse it"
- **Inputs:** email, mixed pdf and xlsx
- **Figure Files not recognised** (`unrecognised_files`): Count of files with no recognised source after the recognise step. Key: Generator: a pack of 5 files, 2 of unknown type.
- **Action and sign-off:** Clerk names the source; Head of Data decides on a new source. Signs: Anita Rao
- **Reuses:** recipes none; skills data.recognise-file, data.detect-duplicate, map.explain-doubt
- **Builds on:** #19
- **New (suggested):** nothing new
- **Pain relieved:** INT-DOC, INT-GOV; KPIs K14

### #61 Data quality score for each source

`uc-061-dqscore` · layer 4 · answer -> Consume

- **Owner:** Anita Rao (head_of_data); with Grace Ong
- **Cadence and trigger:** monthly; Month end
- **Decision:** Which of our sources is the least reliable this month?
- **Question:** "Which source to fix first"
- **Inputs:** all loaded files
- **Figure Quality score per source** (`source_quality`): Share of loads that passed adds-up, were on time, and needed no manual fix. Key: Generator: run log with planted failures per source.
- **Action and sign-off:** Head of Data raises the worst source with its owner. Signs: none (read only)
- **Reuses:** recipes none; skills check.adds-up, consume.build-board
- **Builds on:** #11, #16, #13
- **New (suggested):** recipe:source_quality
- **Pain relieved:** INT-TRUST, INT-DATAGOV; KPIs K02, K07, K12, K19

### #62 FX forwards: upcoming value dates and mark to market

`uc-062-fxlife` · layer 3 · watch -> Action

- **Owner:** Sam Lee (ops_clerk); with Daniel Foo, Grace Ong
- **Cadence and trigger:** weekly; Weekly, and 5 days before a value date
- **Decision:** Which FX forwards settle in the next 30 days and what are they worth now?
- **Question:** "Which forwards need settlement cash or a roll"
- **Inputs:** fx confirmation pdf, fx rate csv, trade export csv
- **Figure Forward mark to market** (`fx_mtm`): Buy amount over spot less sell amount, per forward. Key: Generator: universe rule: buy / spot - sell; two forwards.
- **Action and sign-off:** Clerk tells the CFO the cash needed on the value date. Signs: Daniel Foo
- **Reuses:** recipes fx_confirmation_variance; skills data.read-pdf-fields, check.against-source, action.size-impact
- **Builds on:** #51
- **New (suggested):** recipe:fx_mtm
- **Pain relieved:** PP-06, INT-RISK, PP-01; KPIs K08, K09, K10, K11

### #63 Unexplained bank lines

`uc-063-cashcode` · layer 5 · watch -> Action

- **Owner:** Sam Lee (ops_clerk); with Grace Ong
- **Cadence and trigger:** daily; Bank file arrives
- **Decision:** Which lines on the bank statement do we not know what they are?
- **Question:** "Which bank lines have no purpose and need coding"
- **Inputs:** bank statement xlsx
- **Figure Bank lines with no purpose** (`uncoded_bank_lines`): Bank lines not matched to any movement or notice. Key: Generator: bank lines minus matched lines; planted 3 unmatched.
- **Action and sign-off:** Clerk codes each line or asks Finance. Signs: Grace Ong
- **Reuses:** recipes cash_break; skills data.match-identity, action.detect-exception, action.route-owner
- **Builds on:** #27, #2
- **New (suggested):** nothing new
- **Pain relieved:** PP-01, PP-06

### #99 Bring in a new source file

`uc-099-newfeed` · layer 5 · act -> Build

- **Owner:** Anita Rao (head_of_data); with Sam Lee
- **Cadence and trigger:** event; A new kind of file is to be used
- **Decision:** We will get a new custodian file. How will it fit the model?
- **Question:** "Whether the new feed is designed, mapped and safe to go live"
- **Inputs:** custody statement pdf, custodian export csv
- **Figure Columns mapped and in doubt** (`feed_mapping`): Share of columns mapped with confidence. Key: Generator: planted file with 2 ambiguous columns.
- **Action and sign-off:** Head of Data approves the mapping. Signs: none (read only)
- **Reuses:** recipes none; skills data.profile-file, map.map-file, map.explain-doubt, model.propose-clean-table
- **Builds on:** #16, #61
- **New (suggested):** nothing new
- **Pain relieved:** INT-DOC, INT-DATAGOV; KPIs K14, K19

## Family and people (11 cards)

### #15 P15 · Family member allowances and distributions due

`uc-015-allowances` · layer 5 · act -> Action

- **Owner:** Mei Chen (principal); with Daniel Foo, Helen Foo
- **Cadence and trigger:** monthly; Month start
- **Decision:** Which family distributions to approve this month and whether cash supports them
- **Question:** "What do we owe each family member this month, and do we have the cash?"
- **Inputs:** family allowance schedule xlsx, administrator cash csv
- **Figure Allowance due by member** (`allowance_due`): Scheduled amount per member for the month less paid to date. Key: Generator schedule rows; paid from generated cash movements.
- **Action and sign-off:** Principal approves, Finance pays. Signs: Mei Chen
- **Reuses:** recipes cash_by_entity; skills data.recognise-file, action.detect-exception, action.route-owner
- **Builds on:** #3, #14
- **New (suggested):** table:family_members, recipe:allowance_due
- **Pain relieved:** INT-LIQ, PP-01, INT-GOV; KPIs K01, K04, K05, K06
- **Signals:**
  - Month start -> Allowance due per family member against paid to date -> Mei Chen: 1 click (approve all)
  - Approved -> Payment list to Finance -> Daniel Foo: 1 click (release)
  - **EXCEPTION** An allowance that the entity cash cannot cover after the buffer -> Held with the shortfall -> Daniel Foo: 1 decision

### #52 Insurance policies and renewals

`uc-052-insurance` · layer 1 · watch -> Action

- **Owner:** Priya Nair (hr_admin); with Mei Chen, Daniel Foo
- **Cadence and trigger:** monthly; A renewal date is within 60 days
- **Decision:** Which policies to renew, change or let lapse
- **Question:** "Which policies expire in the next 60 days and what is each worth?"
- **Inputs:** insurance schedule pdf
- **Figure Policies expiring in 60 days** (`renewals_due`): Policies with end date within 60 days of today. Key: Generator policy table; date arithmetic.
- **Action and sign-off:** HR drafts the renewal request for Principal approval. Signs: Mei Chen
- **Reuses:** recipes none; skills data.read-pdf-fields, action.detect-exception, action.draft-message
- **Builds on:** nothing (a basic)
- **New (suggested):** table:insurance_policies, recipe:renewals_due
- **Pain relieved:** PP-08, INT-GOV

### #81 Household and office payroll

`uc-081-payroll` · layer 6 · act -> Action

- **Owner:** Priya Nair (hr_admin); with Daniel Foo
- **Cadence and trigger:** monthly; Payroll date approaches
- **Decision:** Is payroll ready to approve and does the cash cover it?
- **Question:** "Whether to release the pay file"
- **Inputs:** payroll register xlsx, bank statement xlsx
- **Figure Payroll total against last month** (`payroll_total`): Sum of net pay and employer costs; change from last month. Key: Generator: universe staff table; sums by month.
- **Action and sign-off:** HR prepares; CFO approves; Operations pays. Signs: Daniel Foo
- **Reuses:** recipes none; skills action.detect-exception, action.route-owner
- **Builds on:** #8
- **New (suggested):** table:staff_payroll, recipe:payroll_total
- **Pain relieved:** INT-PAY, INT-GOV; KPIs K16, K18

### #82 Insurance cover against what we own

`uc-082-covergap` · layer 3 · answer -> Consume

- **Owner:** Priya Nair (hr_admin); with Helen Foo, Mei Chen
- **Cadence and trigger:** yearly; Annual renewal
- **Decision:** Are our properties and art insured for what they are worth?
- **Question:** "Whether to raise or lower cover"
- **Inputs:** insurance schedule pdf, property valuation pdf
- **Figure Insured value less asset value** (`cover_gap`): Sum insured less latest appraisal per asset. Key: Generator: universe policies and appraisals.
- **Action and sign-off:** HR takes the gap to the Principal. Signs: Mei Chen
- **Reuses:** recipes real_asset_value; skills check.against-source, consume.answer-question
- **Builds on:** #52, #65
- **New (suggested):** nothing new
- **Pain relieved:** INT-RISK, PP-08; KPIs K08, K09, K10, K11

### #83 Tax calendar

`uc-083-taxcal` · layer 1 · watch -> Action

- **Owner:** Helen Foo (fund_accountant); with Daniel Foo, Priya Nair
- **Cadence and trigger:** weekly; Every Monday
- **Decision:** Which tax filings and payments fall due in the next 60 days?
- **Question:** "Which filings and payments are due and who prepares them"
- **Inputs:** tax notice pdf
- **Figure Tax items due in 60 days** (`tax_due`): Items with due date inside 60 days, by entity. Key: Generator: universe tax calendar.
- **Action and sign-off:** Fund Accountant confirms preparer; CFO approves payment. Signs: Daniel Foo
- **Reuses:** recipes none; skills action.detect-exception, action.route-owner
- **Builds on:** nothing (a basic)
- **New (suggested):** table:tax_obligations, recipe:tax_due
- **Pain relieved:** PP-08, INT-GOV

### #84 Estimated tax for the year

`uc-084-taxest` · layer 4 · answer -> Consume

- **Owner:** Daniel Foo (cfo); with Helen Foo
- **Cadence and trigger:** quarterly; Quarter end
- **Decision:** How much tax do we expect to owe this year?
- **Question:** "How much cash to set aside for tax"
- **Inputs:** trade export csv, tax notice pdf
- **Figure Estimated tax** (`tax_estimate`): Realised gains and income times rate by entity, less credits. Key: Generator: generator rates and realised trades.
- **Action and sign-off:** CFO sets cash aside. Signs: none (read only)
- **Reuses:** recipes none; skills build.write-formula-table, consume.answer-question
- **Builds on:** #67, #68, #83
- **New (suggested):** recipe:tax_estimate
- **Pain relieved:** PP-08, INT-LIQ; KPIs K01, K04, K05, K06

### #85 Philanthropy: budget used

`uc-085-grants` · layer 6 · answer -> Consume

- **Owner:** Mei Chen (principal); with Daniel Foo
- **Cadence and trigger:** quarterly; Quarter end
- **Decision:** How much of this year giving budget have we spent and pledged?
- **Question:** "Whether to approve more grants this year"
- **Inputs:** grant ledger xlsx
- **Figure Paid and pledged against budget** (`grants_used`): Paid plus pledged grants over the annual budget. Key: Generator: universe grant table.
- **Action and sign-off:** Principal decides new grants. Signs: none (read only)
- **Reuses:** recipes none; skills consume.answer-question
- **Builds on:** #54
- **New (suggested):** table:grants, recipe:grants_used
- **Pain relieved:** INT-LIQ, INT-GOV; KPIs K01, K04, K05, K06

### #86 Approve a grant payment

`uc-086-grantappr` · layer 7 · act -> Action

- **Owner:** Mei Chen (principal); with Daniel Foo, Priya Nair
- **Cadence and trigger:** event; A grant request arrives
- **Decision:** This charity asked for 50,000. Is it within the budget and have we checked it?
- **Question:** "Whether to pay the grant"
- **Inputs:** grant request pdf, email
- **Figure Budget, charity check, cash** (`grant_check`): Grant against remaining budget; registration date; cash cover. Key: Generator: grant table and cash.
- **Action and sign-off:** Principal approves; Finance pays. Signs: Mei Chen
- **Reuses:** recipes none; skills action.size-impact, action.route-owner
- **Builds on:** #85, #54
- **New (suggested):** table:grants
- **Pain relieved:** INT-GOV, INT-LIQ; KPIs K01, K04, K05, K06

### #87 Trust distributions to beneficiaries

`uc-087-trustdist` · layer 6 · act -> Action

- **Owner:** Helen Foo (fund_accountant); with Mei Chen, Daniel Foo
- **Cadence and trigger:** quarterly; Quarter end
- **Decision:** What can the Family Trust pay each beneficiary this quarter under the deed?
- **Question:** "Whether the trust pays what its deed allows"
- **Inputs:** trust deed pdf, administrator cash csv
- **Figure Distribution room per beneficiary** (`trust_distribution_room`): Deed share times distributable income less paid. Key: Generator: universe trust deed terms and paid.
- **Action and sign-off:** Principal signs; trustee pays. Signs: Mei Chen
- **Reuses:** recipes none; skills intent.read-company-doc, action.size-impact, action.route-owner
- **Builds on:** #38
- **New (suggested):** table:succession_plan, table:family_members
- **Pain relieved:** INT-SCOPE, INT-GOV

### #88 Cash for an estate or transfer tax

`uc-088-estateliq` · layer 6 · answer -> Consume

- **Owner:** Mei Chen (principal); with Daniel Foo
- **Cadence and trigger:** yearly; Year end
- **Decision:** If the worst happened, could we pay the tax without selling the property?
- **Question:** "Whether the family could meet a transfer tax from liquid assets"
- **Inputs:** trust deed pdf
- **Figure Tax need against liquid assets** (`estate_cash_need`): Estimated tax on estate value against liquid assets after debt. Key: Generator: universe values and rate.
- **Action and sign-off:** Principal reviews with the family advisers. Signs: none (read only)
- **Reuses:** recipes net_worth_after_debt, real_asset_value; skills build.write-formula-table, consume.answer-question
- **Builds on:** #17, #65, #54
- **New (suggested):** recipe:estate_cash_need
- **Pain relieved:** INT-LIQ, INT-SCOPE; KPIs K01, K04, K05, K06

### #100 What each family member can see

`uc-100-famaccess` · layer 8 · act -> Action

- **Owner:** Priya Nair (hr_admin); with Mei Chen, Anita Rao
- **Cadence and trigger:** event; A family member is added to reports
- **Decision:** Our daughter wants to see her trust. What should she see?
- **Question:** "What each family member may see"
- **Inputs:** access request email
- **Figure Access per family member** (`member_access`): Reports and entities shown against the policy. Key: Generator: member table with planted 1 over-grant.
- **Action and sign-off:** Principal approves. Signs: Mei Chen
- **Reuses:** recipes none; skills intent.set-access, action.route-owner
- **Builds on:** #92, #15, #74
- **New (suggested):** table:family_members, table:access_grants
- **Pain relieved:** INT-GOV, INT-DATAGOV; KPIs K19

## Run the office (13 cards)

### #9 P9 TESTED · Process map and SOP for the month-end report

`uc9-sop` · layer 1 · process -> Knowledge

- **Owner:** Priya Nair (hr_admin); with Mei Chen, Grace Ong
- **Cadence and trigger:** event; A process is done from memory
- **Decision:** Whether the written procedure is right to hand to a new joiner
- **Question:** "What are the steps of the month-end report process and who does each one?"
- **Inputs:** process narrative md, email
- **Figure Steps, owners and checks** (`process_steps`): Count of steps with a named owner, system and check. Key: Existing: the SOP exists and names the steps and owners.
- **Action and sign-off:** HR Manager publishes the SOP. Signs: Mei Chen
- **Reuses:** recipes none; skills intent.read-company-doc, intent.draw-process-lanes, intent.draw-process-steps, intent.map-decision-path, intent.write-sop
- **Builds on:** nothing (a basic)
- **New (suggested):** nothing new
- **Pain relieved:** INT-OPS, INT-DATAGOV, INT-GOV; KPIs K03, K19
- **Signals:**
  - Process narrative and the handover email -> Steps, lanes, hand-overs, checks and failure handling drawn -> Priya Nair: 1 click (accept)
  - SOP drafted -> Procedure document for a new joiner -> Priya Nair: 1 click (publish)
  - **EXCEPTION** A step with no owner or no check -> Listed as a gap before the SOP can be signed -> Priya Nair: 1 call to Mei

### #30 P30 · Vendors and contract renewals

`uc-030-vendors` · layer 1 · watch -> Action

- **Owner:** Priya Nair (hr_admin); with Daniel Foo
- **Cadence and trigger:** monthly; A contract renewal is within 90 days
- **Decision:** Which vendor contracts renew in the next 90 days and what do they cost?
- **Question:** "Which contracts to renew, renegotiate or end"
- **Inputs:** vendor contract pdf
- **Figure Contracts renewing in 90 days** (`renewals_vendors`): Contracts with renewal date inside 90 days; annual cost. Key: Generator: universe vendor table.
- **Action and sign-off:** HR proposes; CFO approves. Signs: Daniel Foo
- **Reuses:** recipes none; skills data.read-pdf-fields, action.detect-exception
- **Builds on:** nothing (a basic)
- **New (suggested):** table:vendor_contracts, recipe:renewals_vendors
- **Pain relieved:** INT-OPS, INT-GOV; KPIs K03
- **Signals:**
  - Vendor contracts loaded -> Contracts renewing in 90 days with annual cost -> Priya Nair: 1 click (propose)
  - Renewal approved -> Next renewal date set -> Daniel Foo: 1 click
  - **EXCEPTION** Auto-renewal date within 30 days and no decision -> Flag with the notice deadline -> Priya Nair: 1 call

### #50 P50 · Administrator and custodian invoices against the fee schedule

`uc-050-feeinv` · layer 8 · act -> Action

- **Owner:** Grace Ong (ops_lead); with Helen Foo, Daniel Foo
- **Cadence and trigger:** monthly; An invoice arrives
- **Decision:** Does the administrator invoice match the fee schedule?
- **Question:** "Whether to pay the invoice as billed"
- **Inputs:** invoice pdf, vendor contract pdf
- **Figure Invoice less expected fee** (`invoice_variance`): Invoice amount less fee schedule rate times base. Key: Generator: invoice from generator with 1 planted overcharge.
- **Action and sign-off:** Operations queries; CFO approves the payment. Signs: Daniel Foo
- **Reuses:** recipes none; skills data.read-pdf-fields, check.against-source, action.draft-message
- **Builds on:** #30, #49
- **New (suggested):** nothing new
- **Pain relieved:** INT-OPS, PP-04, INT-GOV; KPIs K03
- **Signals:**
  - Administrator invoice arrives -> Invoice against the fee schedule rate times base -> Grace Ong: 1 click (approve)
  - Invoice matches -> Moves to the payment run -> nobody: see it, no work
  - **EXCEPTION** Invoice higher than the schedule -> Held with the difference and a query draft -> Grace Ong: 1 click (send query)

### #89 Expense approval and sign-off rules

`uc-089-expapp` · layer 6 · process -> Knowledge

- **Owner:** Priya Nair (hr_admin); with Daniel Foo, Mei Chen
- **Cadence and trigger:** yearly; Annual review
- **Decision:** Who can approve what amount, and are we following it?
- **Question:** "Which approval limits to set and who may approve"
- **Inputs:** expense ledger xlsx, policy pdf
- **Figure Payments over their approval limit** (`approval_exceptions`): Payments above the approver limit. Key: Generator: payment table with 2 planted over-limit.
- **Action and sign-off:** HR updates the rules; Principal signs. Signs: Mei Chen
- **Reuses:** recipes none; skills intent.map-decision-path, intent.write-sop, action.detect-exception
- **Builds on:** #8
- **New (suggested):** nothing new
- **Pain relieved:** INT-GOV

### #90 What the office costs

`uc-090-offcost` · layer 7 · answer -> Consume

- **Owner:** Daniel Foo (cfo); with Priya Nair, Mei Chen
- **Cadence and trigger:** monthly; Month end
- **Decision:** What does it cost to run the office, by type, against budget?
- **Question:** "Whether the office costs more than planned"
- **Inputs:** expense ledger xlsx, payroll register xlsx, invoice pdf
- **Figure Cost by type against budget** (`office_cost`): Sum of staff, vendors, fees, other, over budget. Key: Generator: universe expenses by category.
- **Action and sign-off:** CFO reports to the Principal. Signs: none (read only)
- **Reuses:** recipes payroll_total; skills build.write-formula-table, consume.answer-question
- **Builds on:** #81, #30
- **New (suggested):** table:office_expenses, recipe:office_cost
- **Pain relieved:** INT-OPS, INT-PAY; KPIs K03, K16, K18

### #91 Joiner, mover, leaver access

`uc-091-jml` · layer 1 · act -> Action

- **Owner:** Priya Nair (hr_admin); with Anita Rao
- **Cadence and trigger:** event; A person joins, moves or leaves
- **Decision:** A new analyst starts Monday. What should they see?
- **Question:** "Which access to give or remove"
- **Inputs:** access request email
- **Figure Access given but not approved** (`access_open`): Grants with no approver recorded. Key: Generator: planted 2 grants without approver.
- **Action and sign-off:** HR requests; Head of Data grants; Principal approves sensitive access. Signs: Mei Chen
- **Reuses:** recipes none; skills intent.set-access, action.route-owner, action.close-with-reason
- **Builds on:** nothing (a basic)
- **New (suggested):** table:access_grants
- **Pain relieved:** INT-GOV, INT-DATAGOV; KPIs K19

### #92 Quarterly access review

`uc-092-accessrev` · layer 2 · act -> Action

- **Owner:** Priya Nair (hr_admin); with Anita Rao, Mei Chen
- **Cadence and trigger:** quarterly; Quarter end
- **Decision:** Who can see what, and does each person still need it?
- **Question:** "Which access to remove"
- **Inputs:** access review csv
- **Figure Access not used in 90 days** (`stale_access`): Grants with no use in 90 days. Key: Generator: planted 3 unused grants.
- **Action and sign-off:** Principal attests; Head of Data removes. Signs: Mei Chen
- **Reuses:** recipes none; skills intent.set-access, action.detect-exception, action.route-owner
- **Builds on:** #91
- **New (suggested):** table:access_grants
- **Pain relieved:** INT-GOV, INT-DATAGOV; KPIs K19

### #93 Onboard a new manager

`uc-093-onbmgr` · layer 7 · act -> Action

- **Owner:** Grace Ong (ops_lead); with Tom Hale, Sofia Reyes, Helen Foo
- **Cadence and trigger:** event; A commitment is approved
- **Decision:** We just committed to a new fund. What do we need before the first call?
- **Question:** "Whether every document and feed is in place before the first call"
- **Inputs:** kyc pack pdf, subscription document pdf
- **Figure Items complete and outstanding** (`onboarding_items`): Checklist for contacts, KYC, bank details, statement schedule. Key: Generator: checklist plus planted 2 missing items.
- **Action and sign-off:** Operations Lead signs off the manager as ready. Signs: Raj Patel
- **Reuses:** recipes none; skills intent.write-sop, action.detect-exception, action.route-owner
- **Builds on:** #34, #35
- **New (suggested):** table:kyc_records, table:expected_statements_schedule
- **Pain relieved:** INT-DOC, INT-GOV, PP-05; KPIs K14

### #94 Open or change a bank or custody account

`uc-094-onbbank` · layer 8 · act -> Action

- **Owner:** Daniel Foo (cfo); with Tom Hale, Grace Ong
- **Cadence and trigger:** event; A new account is needed
- **Decision:** We want to open an account at a new bank. What must be done and who signs?
- **Question:** "Whether the account and its signatories are approved"
- **Inputs:** bank form pdf, policy pdf
- **Figure Setup steps and signatories** (`account_setup`): Checklist; signatories against the signing policy. Key: Generator: planted 1 missing signatory.
- **Action and sign-off:** CFO and Principal sign. Signs: Mei Chen
- **Reuses:** recipes none; skills intent.write-sop, action.route-owner
- **Builds on:** #10, #93
- **New (suggested):** table:bank_accounts, table:kyc_records
- **Pain relieved:** INT-GOV, INT-SCOPE

### #95 SOPs not reviewed in a year

`uc-095-sopreview` · layer 2 · watch -> Action

- **Owner:** Priya Nair (hr_admin); with Anita Rao
- **Cadence and trigger:** quarterly; Quarter end
- **Decision:** Which of our written procedures are out of date?
- **Question:** "Which procedures to review"
- **Inputs:** sop md
- **Figure SOPs by last review** (`sop_age`): Age of last review; flagged above 365 days. Key: Generator: universe SOP table.
- **Action and sign-off:** HR assigns the review. Signs: none (read only)
- **Reuses:** recipes process_steps; skills action.detect-exception, action.route-owner
- **Builds on:** #9
- **New (suggested):** nothing new
- **Pain relieved:** INT-OPS, INT-DATAGOV; KPIs K03, K19

### #96 Which processes to automate next

`uc-096-automation` · layer 6 · answer -> Consume

- **Owner:** Anita Rao (head_of_data); with Priya Nair, Grace Ong
- **Cadence and trigger:** quarterly; Quarter end
- **Decision:** Which manual steps take the most time and fail the most?
- **Question:** "Which process to automate"
- **Inputs:** sop md, exception log
- **Figure Time and failures per step** (`automation_score`): Minutes per run times runs, plus failures, by SOP step. Key: Generator: step durations in the process map and failures in the exception log.
- **Action and sign-off:** Head of Data proposes; Principal approves the build. Signs: Mei Chen
- **Reuses:** recipes none; skills intent.draw-process-steps, consume.build-board
- **Builds on:** #9, #61, #59
- **New (suggested):** recipe:automation_score
- **Pain relieved:** INT-OPS, INT-DATAGOV; KPIs K03, K19

### #97 Know-your-client documents expiring

`uc-097-kycrefresh` · layer 9 · watch -> Action

- **Owner:** Tom Hale (risk_officer); with Priya Nair, Grace Ong
- **Cadence and trigger:** yearly; A document is within 90 days of expiry
- **Decision:** Which KYC documents expire soon?
- **Question:** "Which documents to refresh before the bank or manager freezes the account"
- **Inputs:** kyc pack pdf
- **Figure Documents expiring in 90 days** (`kyc_expiry`): Expiry date minus today. Key: Generator: universe KYC table.
- **Action and sign-off:** Risk Officer asks the owner to supply. Signs: none (read only)
- **Reuses:** recipes none; skills action.detect-exception, action.draft-message
- **Builds on:** #93, #94
- **New (suggested):** table:kyc_records
- **Pain relieved:** INT-GOV, PP-08

### #98 Keep the office words in step with the model

`uc-098-wordlist` · layer 3 · process -> Knowledge

- **Owner:** Anita Rao (head_of_data); with Mei Chen
- **Cadence and trigger:** monthly; A new term appears in a question or a document
- **Decision:** The team keeps saying dry powder. Is that the same as uncalled?
- **Question:** "Whether to add a word to the language list"
- **Inputs:** email, meeting notes md
- **Figure Terms proposed and accepted** (`terms_proposed`): Count of new words proposed and accepted. Key: Generator: planted 4 terms, 2 already in the list.
- **Action and sign-off:** Head of Data accepts or rejects. Signs: none (read only)
- **Reuses:** recipes none; skills consume.understand-words, knowledge.learn-word
- **Builds on:** #11, #16
- **New (suggested):** nothing new
- **Pain relieved:** INT-DATAGOV; KPIs K19

## New figures, tables and recipes needed (suggested), ranked by cards that need them

| Count | Item | Cards (#) |
|---|---|---|
| 3 | `table:access_grants` | 91, 92, 100 |
| 3 | `table:bank_accounts` | 6, 10, 94 |
| 3 | `table:committee_decisions` | 33, 40, 47 |
| 3 | `table:family_members` | 15, 87, 100 |
| 3 | `table:fund_notices` | 1, 2, 37 |
| 3 | `table:kyc_records` | 93, 94, 97 |
| 2 | `table:deal_pipeline` | 34, 77 |
| 2 | `table:expected_statements_schedule` | 19, 93 |
| 2 | `table:grants` | 85, 86 |
| 2 | `table:office_expenses` | 73, 90 |
| 2 | `table:payments` | 4, 8 |
| 2 | `table:policy_limits` | 32, 48 |
| 1 | `figure:private_markets_budget` | 7 |
| 1 | `recipe:actions_next_14d` | 55 |
| 1 | `recipe:allocation` | 31 |
| 1 | `recipe:allowance_due` | 15 |
| 1 | `recipe:attribution` | 46 |
| 1 | `recipe:automation_score` | 96 |
| 1 | `recipe:bank_details_changed` | 5 |
| 1 | `recipe:called_to_date` | 2 |
| 1 | `recipe:cash_after_calls` | 4 |
| 1 | `recipe:cash_by_bank` | 10 |
| 1 | `recipe:cash_forecast` | 72 |
| 1 | `recipe:cash_runway` | 73 |
| 1 | `recipe:close_items_done` | 29 |
| 1 | `recipe:commitments_by_fund` | 7 |
| 1 | `recipe:currency_exposure` | 64 |
| 1 | `recipe:ddq_compare` | 35 |
| 1 | `recipe:distribution_gap` | 37 |
| 1 | `recipe:estate_cash_need` | 88 |
| 1 | `recipe:expected_distributions` | 71 |
| 1 | `recipe:fee_drag` | 49 |
| 1 | `recipe:fund_irr_tvpi` | 39 |
| 1 | `recipe:funding_plan` | 18 |
| 1 | `recipe:fx_mtm` | 62 |
| 1 | `recipe:fx_required` | 6 |
| 1 | `recipe:grants_used` | 85 |
| 1 | `recipe:income_forecast` | 68 |
| 1 | `recipe:intercompany_balance` | 28 |
| 1 | `recipe:liquid_pnl_mtd` | 43 |
| 1 | `recipe:liquidity_ladder` | 54 |
| 1 | `recipe:lookthrough_exposure` | 69 |
| 1 | `recipe:manager_score` | 76 |
| 1 | `recipe:nav_rollforward` | 38 |
| 1 | `recipe:net_worth_after_debt` | 17 |
| 1 | `recipe:networth_walk` | 75 |
| 1 | `recipe:office_cost` | 90 |
| 1 | `recipe:payment_batch` | 8 |
| 1 | `recipe:payroll_total` | 81 |
| 1 | `recipe:position_break` | 56 |
| 1 | `recipe:price_gap_pct` | 57 |
| 1 | `recipe:real_asset_value` | 65 |
| 1 | `recipe:renewals_due` | 52 |
| 1 | `recipe:renewals_vendors` | 30 |
| 1 | `recipe:source_quality` | 61 |
| 1 | `recipe:tax_due` | 83 |
| 1 | `recipe:tax_estimate` | 84 |
| 1 | `recipe:time_weighted_return` | 42 |
| 1 | `recipe:twr_periods` | 44 |
| 1 | `recipe:unrealised_gain` | 67 |
| 1 | `recipe:unsettled_trades` | 58 |
| 1 | `recipe:value_age_days` | 21 |
| 1 | `recipe:watch_flags` | 53 |
| 1 | `skill:read-capital-call-notice` | 1 |
| 1 | `table:audit_requests` | 24 |
| 1 | `table:corporate_actions` | 55 |
| 1 | `table:counterparties` | 10 |
| 1 | `table:credit_facilities` | 17 |
| 1 | `table:custody_positions` | 56 |
| 1 | `table:fee_charges` | 49 |
| 1 | `table:fee_schedules` | 49 |
| 1 | `table:fund_holdings` | 69 |
| 1 | `table:fund_terms` | 78 |
| 1 | `table:instrument_identifiers_gaps` | 13 |
| 1 | `table:insurance_policies` | 52 |
| 1 | `table:intercompany` | 28 |
| 1 | `table:office_rules` | 4 |
| 1 | `table:prices_second_source` | 57 |
| 1 | `table:real_assets` | 65 |
| 1 | `table:settlements` | 58 |
| 1 | `table:staff_payroll` | 81 |
| 1 | `table:standing_instructions` | 5 |
| 1 | `table:succession_plan` | 87 |
| 1 | `table:tax_lots` | 67 |
| 1 | `table:tax_obligations` | 83 |
| 1 | `table:vendor_contracts` | 30 |

Existing and reused: recipes net_worth, cash_by_entity, cash_break, missing_statements, concentration, change_since_report, fx_confirmation_variance; tables in `evidence-to-action-mvp.dbml` (fx_confirmations and expected_statements already there). `table:expected_statements_schedule` and `table:fund_notices` extend them.

## How the picture grows

Cumulative after each block of cards in build order: distinct figures, distinct source kinds (file kinds), distinct decisions, and distinct people involved.

| After card | Figures | Source kinds | Decisions | People acting | Max layer |
|---|---|---|---|---|---|
| 1 | 2 | 2 | 1 | 3 | 1 |
| 3 | 7 | 4 | 3 | 6 | 3 |
| 7 | 16 | 8 | 7 | 7 | 6 |
| 10 | 19 | 11 | 10 | 9 | 6 |
| 20 | 29 | 18 | 20 | 10 | 6 |
| 30 | 39 | 25 | 30 | 10 | 6 |
| 40 | 49 | 27 | 40 | 10 | 7 |
| 50 | 59 | 31 | 50 | 10 | 8 |
| 60 | 69 | 35 | 60 | 10 | 8 |
| 70 | 79 | 38 | 70 | 10 | 8 |
| 80 | 89 | 39 | 80 | 10 | 8 |
| 90 | 99 | 45 | 90 | 10 | 8 |
| 100 | 109 | 52 | 100 | 10 | 9 |
