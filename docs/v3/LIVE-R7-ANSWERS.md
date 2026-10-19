# Round 7 live answers: review

Source: `D:/Temp/sh3-live/r7/` (one JSON per build, read in full). Spec: `packs/family_office/1/use_cases_100.yaml`. Each answer was read as the family-office person who asked. Checker `pass` flags were checked against the answer text, not taken on trust.

## 1. Headline counts

- Builds reviewed: 100 (all 100 use cases in the spec have an answer file; the morning note is one of them).
- No answer: 3 builds stopped on a data or syntax error (uc-055, uc-075, uc-099).
- Verdict: Pass 28, Fix wording 14, Partial 34, Fail 24.
- Wrong or missing answer to the question asked: 24.
- Plain-words failures: 46 builds.
- Leaks: 4 builds (test-answer wording in uc-041; internal build names in three stuck messages). No real client, other-project or credential names found.
- Checker: pass 79, fail 18, no answer 3. Of the 79 passes, 14 show expected values that are not in the answer text, so the checker is not a reliable signal.

## 2. One row per use case

Correct? and Answers it? are judged against the question asked (`check.ask`). Verdict: Fail if the answer is wrong or missing; Partial if it is right but incomplete; Fix wording if correct but plain-words or leak issues; otherwise Pass.

| # | Build | Person | Question asked | Correct? | Answers it? | Plain words? | Leaks | Verdict | Note |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `morning-networth-note` | Mei Chen | What are we worth in the latest report? | Partly | Yes | Fail | None | Partial | Figure matches the September report, but other answers give family totals of 105m to 131m. Scope of 57.6m not stated. Unlabelled SGD total and file name shown. |
| 2 | `uc-001-noticelog` | Sam Lee | A Cedarpoint call notice just came in by email. Which fund, how much and by when? | Yes | Yes | Pass | None | Fix wording | Correct call. Says 5,950,000 of earlier calls paid; uc-002 says 6,000,000 called before call 7. One of them is wrong. |
| 3 | `uc-002-callrecord` | Helen Foo | Does call 7 fit what we committed to Cedarpoint Ventures III, and what is left after it? | Yes | Yes | Pass | None | Pass | Correct: 6,000,000 of 10,000,000 called, 7,250,000 after call 7, 2,750,000 unfunded. |
| 4 | `uc-004-callcheck` | Daniel Foo | Can Holdings pay the Cedarpoint call on the 23rd? | Yes | Yes | Fail | None | Fix wording | Right answer: short USD 270,000, convert SGD 361,800. Units missing: the 1.34 rate has no pair and the 1,600,000 has no currency. |
| 5 | `uc-005-benefcheck` | Grace Ong | Cedarpoint now says to wire to an account ending 4471. Is that really them? | No | No | Fail | None | Fail | Does not answer whether the account is genuine. Gives no 2209 (the account on file). Shows a net-worth list instead. Checker passes only because 4471 appears. |
| 6 | `uc-006-fxneed` | Grace Ong | We hold SGD and need USD for the call. How much do we convert, and did the bank trade at the right rate? | Partly | Partly | Fail | None | Partial | Amount right. Does not show the bank's confirmation (rate 1.3405, SGD 361,935); gives an average over '9 conversions' instead. Repeats the uc-004 text. |
| 7 | `uc-007-pacing` | Raj Patel | What's our unfunded commitment across all funds? | Yes | Partly | Pass | None | Partial | Total right: 14,600,000 unfunded. No per-fund split and no source file, which the signal asks for. |
| 8 | `uc-008-payrun` | Grace Ong | Which payments to release | Yes | Yes | Fail | None | Fix wording | Right release/hold decisions. '(synthetic)' tags on payee names. |
| 9 | `uc-010-bankexp` | Tom Hale | Whether too much cash sits at one bank | Yes | Partly | Fail | None | Partial | Figures right. No verdict: says the policy sets no bank limit, so 'too much' is not answered. '(synthetic)' tags. |
| 10 | `uc-013-secgaps` | Anita Rao | Which instruments need a class or identifier before limits and allocation can be trusted? | Yes | Yes | Pass | None | Pass | Correct. Wording repeats the total; 4-decimal percentage is more precise than needed. |
| 11 | `uc-015-allowances` | Mei Chen | What do we owe each family member this month, and do we have the cash? | No | No | Pass | None | Fail | Answers September for one person and lists four as paid for October. No cash answer. Checker fails. |
| 12 | `uc-016-schemadrift` | Anita Rao | The administrator renamed a column. What breaks, and is the new mapping safe? | Partly | Partly | Fail | None | Partial | Rename found, but says nothing on whether the mapping is safe. Table and column names shown ('position_snapshots.source_market_value', 'renamed: 1'). |
| 13 | `uc-017-liab` | Mei Chen | What do we owe, and what is our net worth after debt? | Yes | Partly | Pass | None | Partial | Total 105,430,000 after 2,800,000 of debt is arithmetically right. No comparison with what the family expects; the debt is not named. Family total differs from other answers. |
| 14 | `uc-018-fundplan` | Daniel Foo | Which entity pays and whether a transfer is needed first | Yes | Yes | Fail | None | Fix wording | Right entity and transfer. No currency on 618,343.96 or -36,104.48. |
| 15 | `uc-021-stale` | Tom Hale | Which fund values are older than 90 days and so not safe to use in limits and reports? | Yes | Yes | Pass | None | Pass | Correct: three fund values older than 90 days, with ages. |
| 16 | `uc-022-amendlog` | Helen Foo | Which earlier value is replaced, and do the reports already issued need a note? | Yes | Partly | Pass | None | Partial | Three amended values listed. Does not say whether issued reports need a note. |
| 17 | `uc-023-tieout` | Helen Foo | Does each number on the report agree with the administrator? | Yes | Yes | Pass | None | Pass | Correct: three lines apart, 15 agree. |
| 18 | `uc-024-audit` | Anita Rao | Does every figure the auditor sampled trace to a source? | Yes | Yes | Pass | None | Pass | Correct: 7 of 8 traced. '(as sampled)' is unclear but not wrong. |
| 19 | `uc-026-stmtadmin` | Helen Foo | Should we accept the administrator value or ask the administrator to correct it? | Partly | Partly | Fail | None | Partial | Six differences listed. No accept-or-correct view. Status labels '(final)', '(Estimate)', '(Carried forward)' shown without explanation. |
| 20 | `uc-028-interco` | Daniel Foo | Which entity lends to which, and how it is recorded | Yes | Yes | Pass | None | Pass | Correct: 600,000 on 5 Aug 2026, reference IC-2026-08-01. |
| 21 | `uc-029-closeck` | Grace Ong | Is the September close complete and can the report start? | Yes | Partly | Pass | None | Partial | 4 of 6 steps done; open items named. Does not say the report cannot start. |
| 22 | `uc-030-vendors` | Priya Nair | Which contracts to renew, renegotiate or end? | Yes | Partly | Pass | None | Partial | Two renewals and notice date given. No renew, renegotiate or end view. |
| 23 | `uc-031-alloc` | Helen Foo | What share of the family is in each asset class, and in each entity? | Yes | Partly | Fail | None | Partial | Entity split right. Asset-class list cut short ('and more in the figures'). The checker passes although 1.04 is not in the answer. |
| 24 | `uc-032-driftrep` | Tom Hale | Which asset classes are outside their policy band? | No | No | Fail | None | Fail | Lists the asset classes INSIDE their band; the question asks which are OUTSIDE. Underscored names; a fund name is shown as an asset class. |
| 25 | `uc-033-breachesc` | Tom Hale | What is the cost to cure the single-name breach? | Yes | Partly | Pass | None | Partial | Cure amount 324,210.53 given. No waive, cure or escalate view. |
| 26 | `uc-034-prospect` | Sofia Reyes | Does the Harborlight fund fit our mandate, and what is its ticket against what we still have uncalled? | Yes | Partly | Pass | None | Partial | Ticket against uncalled (13.7%, 16.6m) right. Mandate fit not tested. |
| 27 | `uc-035-ddq` | Sofia Reyes | Which answers differ between the Cedarpoint 2025 and 2026 questionnaires? | Yes | Yes | Pass | None | Pass | Correct: five changes between questionnaires. |
| 28 | `uc-037-distrack` | Sam Lee | Whether money promised by a fund has arrived | Yes | Yes | Pass | None | Pass | Correct: 12,500 short on Evergreen Growth I, five others in full. |
| 29 | `uc-038-navroll` | Helen Foo | Is the new value of each private fund explained by calls, distributions and gain? | Partly | Yes | Fail | None | Partial | The 12,500 gap is right, but 'not explained by -12,500' is wrong wording. Expected totals 1,176,980 and -875,000 are not shown. |
| 30 | `uc-039-irr` | Sofia Reyes | Which funds earned their place and which should we stop adding to? | No | No | Fail | None | Fail | No keep-or-stop verdict. IRR and multiple point opposite ways for 5 of 8 funds (e.g. Cedarpoint Ventures III: -40.54% IRR but 1.38x). IRR and TVPI are not defined. |
| 31 | `uc-040-icmemo` | Sofia Reyes | What figures support recommending the Cedarpoint Ventures III commitment? | Yes | Partly | Pass | None | Partial | Figure pack, 17 of 17 traced. No recommendation. Cedarpoint Ventures III is already committed, so the question needs a second look. |
| 32 | `uc-041-commitappr` | Raj Patel | Does the Harborlight commitment fit our budget, limits and cash? | No | No | Fail | 'answer key' wording shown ('the assumption of the answer key') | Fail | Garbled. No verdict on budget, limit or cash. 'short' has no amount. Expected 2,000,000, 16,600,000 and 37.08 are absent. |
| 33 | `uc-043-liquidpnl` | Raj Patel | How much has the liquid book made or lost so far this month? | No | No | Fail | None | Fail | Gives one day's P&L (-11,100) for 1 of 8 portfolios, not month to date. '1 portfolios loaded (of 8)'. Expected 42,273,700 and 1,084,800 absent. |
| 34 | `uc-044-twr` | Raj Patel | What to report on performance for the quarter and the year? | Partly | Yes | Pass | None | Partial | Quarter and year figures given. YTD, last 12 months and all months show the same 3.821% and 5.7563%, which suggests one window labelled three ways. Expected 0.2958 absent. |
| 35 | `uc-045-reportpack` | Raj Patel | Whether to sign off and issue the report: which sections are ready? | Yes | Yes | Pass | None | Pass | Correct: 2 of 5 sections ready, three named as not ready. Checker expects 60, which is the same fact read the other way. |
| 36 | `uc-046-attrib` | Sofia Reyes | Which allocation or selection decision to change? | No | No | Fail | None | Fail | Does not name a decision to change. Parts add to -0.169%, but the stated total is -0.1169%. Underscored names. |
| 37 | `uc-047-icpack` | Raj Patel | Which matters to put to the committee and what to recommend? | Partly | Partly | Fail | None | Partial | Committee items listed but no recommendation. Breaches say 7 real breaches, while uc5 and uc-033 say one. Expected 4.17%, 2.71%, 270,000 and 2,000,000 absent. |
| 38 | `uc-048-policyupd` | Tom Hale | Which limits to change and by how much? | No | No | Fail | None | Fail | Proposes no limit change. Lists cash lines as 'issuers' at 100%. Expected 6.13, 5.89, 5.74 and 5.71 absent. |
| 39 | `uc-049-feedrag` | Helen Foo | Does each manager earn its fees? | Partly | Partly | Pass | None | Partial | Fees and net gains for four managers; Bluewater 9,375 above terms. No verdict on whether each earns its fees. |
| 40 | `uc-050-feeinv` | Grace Ong | Whether to pay the invoice as billed? | Yes | Yes | Pass | None | Pass | Correct: hold Anchorage 1,030 above the 5,150 expected; pay three. |
| 41 | `uc-052-insurance` | Priya Nair | Which policies expire in the next 60 days and what is each worth? | No | Partly | Fail | None | Fail | Values read USD 0, SGD 0, SGD 1, USD 1 (units wrong). No expiry dates. Two extra policies listed. 'None' shown for linked asset. |
| 42 | `uc-053-watchlist` | Sofia Reyes | Which managers have given us a late, restated or changed statement this quarter? | Partly | Yes | Pass | None | Partial | Four managers named correctly. Window starts 16 Jul, not 15 Jul; zero-count lines add noise. |
| 43 | `uc-054-ladder` | Daniel Foo | How much cash do we have against calls and payments in the next 30, 60 and 90 days? | Yes | Partly | Pass | None | Partial | Numbers present, but a sentence dump with no total per window. 'Cash after' ignores the 250,000 buffer that uc-004 and uc-070 apply. |
| 44 | `uc-055-corpact` | Sam Lee | Which actions need a decision or a booking? (build stopped) | No | No | Fail | gold_ build name and error text shown to the user | Fail | No answer: the build stopped on a data error (a 'not available' text value). Internal names shown. |
| 45 | `uc-056-custrecon` | Grace Ong | Which holdings differ between the custodian and the administrator, and why? | Yes | Yes | Pass | None | Pass | Correct: Bay Street Utilities and Redwood Pharma, with reasons. Sign convention on the first line is unclear. |
| 46 | `uc-057-pricecheck` | Grace Ong | Which prices differ from a second source by more than tolerance? | No | No | Fail | None | Fail | Lists about 50 price gaps; tolerance not stated or applied. Expected 22.01 absent. 'gap pct' and .SYN codes shown; percentages have no % sign. |
| 47 | `uc-058-settle` | Sam Lee | Which trades failed to settle and whom do I chase? | Yes | Yes | Fail | None | Fix wording | Correct: two trades, reasons, whom to chase. '(Synthetic Broker Two)' label. |
| 48 | `uc-059-breakage` | Grace Ong | Which breaks are older than five days and go to Finance? | Yes | Partly | Pass | None | Partial | Four old breaks named. Does not say which go to Finance; also lists newer breaks. |
| 49 | `uc-060-docinbox` | Sam Lee | Where does each unrecognised file belong, or should I refuse it? | Yes | Yes | Fail | None | Fix wording | Right routing. Table names (bank_statements, notices) shown; '(SYNTHETIC)' tag; quotes the content of an unrecognised file (venue and table count). |
| 50 | `uc-061-dqscore` | Anita Rao | Which source should I fix first? | Yes | Yes | Fail | None | Fix wording | Correct: administrator_cash, 71.4%. Source names underscored; 'added up and unfixed' is unclear. |
| 51 | `uc-062-fxlife` | Sam Lee | Which forwards need settlement cash or a roll, and what are they worth now? | No | No | Pass | None | Fail | Shows a mismatch, not value now. Notional USD 5,000,000 missing. No settlement-cash or roll decision. |
| 52 | `uc-063-cashcode` | Sam Lee | Which bank lines have no purpose and need coding? | Partly | Yes | Fail | None | Partial | Three lines right; net total 42,120 missing. 'payee Unknown payee' wording. |
| 53 | `uc-064-fxexp` | Tom Hale | Whether to hedge a currency exposure? | Yes | Partly | Fail | None | Partial | Exposures right. No hedge view. 'sold 0' and 'held' with no currency; 'the bank confirms the forwards 8,100 apart' is unclear. |
| 54 | `uc-065-realassets` | Mei Chen | What real assets we own, their values and who holds them? | Yes | Yes | Fail | None | Fix wording | Totals right (17,990,298.50). Each line repeats a garbled template with wrong subtotals. |
| 55 | `uc-066-propreval` | Mei Chen | Whether to order a new appraisal? | Yes | Yes | Pass | None | Pass | Correct: fine art (784 days) and wine (378 days) due; four not yet due. |
| 56 | `uc-067-unrl` | Helen Foo | Which lots to sell for a tax or rebalance reason? | Partly | Partly | Fail | None | Partial | Long. Lot IDs shown; 'oldest lot ... 416,700' is a value with no label. Says seven names are over 5% in the liquid book; uc5 and uc-033 say one. |
| 57 | `uc-068-incomef` | Helen Foo | How much income to plan for next year? | Yes | Yes | Fail | None | Fix wording | Correct: 811,406.60 over 54 payments. No currency given (USD assumed). |
| 58 | `uc-069-lookthru` | Sofia Reyes | Whether the family is over-exposed to one company or sector through funds? | Yes | Partly | Pass | None | Partial | Top exposures given. No verdict on over-exposure; no look-through limit on record. |
| 59 | `uc-070-idle` | Daniel Foo | How much cash is sitting idle above what we need for 90 days? | Yes | Yes | Pass | None | Pass | Correct: 3,588,706.99 idle above the 90-day need and buffer. |
| 60 | `uc-071-expdist` | Sofia Reyes | How much money should we expect back from the funds over the next year? | No | No | Fail | None | Fail | No answer. 'ready tables' is internal jargon. |
| 61 | `uc-072-cashfc` | Daniel Foo | Whether the family needs to raise cash | No | No | Pass | None | Fail | Answers the allowances question (September owed to Ethan Chen) instead of the 12-month cash forecast. Checker fails. |
| 62 | `uc-073-runway` | Mei Chen | Whether spending is sustainable | Partly | Yes | Pass | None | Partial | 25.23 months on cash is right. The 198.5 months counts the USD 42.3m liquid book as spendable money, which overstates runway. Long spend list. |
| 63 | `uc-074-boardpack` | Mei Chen | What to tell the board of the family? | No | No | Fail | None | Fail | Headline figures missing (77,253,120; 3.5148; 5.7563; cash; 270,000; 14.6m). Lists labels with no figures; '2026Q3 in September 2026' contradicts itself; 'estimated' given with no reason. |
| 64 | `uc-075-yearwalk` | Mei Chen | What to tell the family about the year? (build stopped) | No | No | Fail | gold_ build name and error text shown to the user | Fail | No answer: the build stopped on a syntax error in the summary step. Internal names shown. |
| 65 | `uc-076-scorecard` | Raj Patel | Which managers should we keep, add to, or exit? | Partly | Yes | Fail | None | Partial | Keep, add and exit verdicts given. 86.8 expected but absent. 'on time 1' and '0.929' are ratios with no %; 'watch flags' is jargon. |
| 66 | `uc-077-deals` | Sofia Reyes | Which deals should we move forward or drop? | Yes | Yes | Pass | None | Pass | Correct: moving forward vs past stage limit. Drop is implied, not stated. |
| 67 | `uc-078-redemption` | Grace Ong | By when must we send the redemption notice and when do we get the cash? | No | No | Pass | None | Fail | Answers cash by entity, not the notice deadline or the payment date. Checker fails on all dates and amounts. |
| 68 | `uc-079-rebalance` | Raj Patel | Which holdings should we sell or buy, and how much? | Yes | Yes | Fail | None | Fix wording | Correct trades and targets. 'listed_equity' underscored; '-5,811,695 (sell)' puts a minus on a sale. |
| 69 | `uc-080-vintage` | Tom Hale | Are our private commitments too bunched in one year? | Yes | Partly | Pass | None | Partial | Spread by year is right. No judgement on whether it is too bunched. |
| 70 | `uc-081-payroll` | Priya Nair | Whether to release the pay file | Yes | Yes | Pass | None | Pass | Correct: release, hold two lines with reasons. |
| 71 | `uc-082-covergap` | Priya Nair | Whether to raise or lower cover | Yes | Yes | Pass | None | Pass | Correct: USD 9.6m short overall; four uninsured, two under-insured. |
| 72 | `uc-083-taxcal` | Helen Foo | Which filings and payments are due and who prepares them | Yes | Yes | Pass | None | Pass | Correct: one overdue, two due within 60 days, preparers named. |
| 73 | `uc-084-taxest` | Helen Foo | How much cash to set aside for tax | Yes | Yes | Fail | None | Fix wording | Correct total 159,156.51. No currency; internal check ID M02b shown; '1 bank statement month(s)' is awkward. |
| 74 | `uc-085-grants` | Mei Chen | Whether to approve more grants this year | Partly | Partly | Fail | None | Partial | Answers one request, not the budget. Budget picture (300,000 budget, 265,000 used, 88.3%) missing. The -70,000 holds only after paying the 50,000 grant, which is not said. No currency. |
| 75 | `uc-086-grantappr` | Mei Chen | Whether to pay the grant | Yes | Yes | Fail | None | Fix wording | Same text as uc-085. Correct for this request; no currency given. |
| 76 | `uc-087-trustdist` | Helen Foo | Whether the trust pays what its deed allows | Yes | Yes | Pass | None | Pass | Correct: Wen Chen 2,297.17 over her share. Some jargon ('room', 'distributable'). |
| 77 | `uc-088-estateliq` | Mei Chen | Whether the family could meet a transfer tax from liquid assets | Partly | Yes | Pass | None | Partial | Cover 2.95x uses 55,879,741.41 of 'liquid assets', which the answer does not build. Liquid book plus cash less debt is about 45.6m. |
| 78 | `uc-089-expapp` | Priya Nair | Which approval limits to set and who may approve | Partly | Partly | Pass | None | Partial | Two breaches found and named. Does not say which limits to set or who may approve above them. |
| 79 | `uc-090-offcost` | Daniel Foo | Whether the office costs more than planned | Yes | Yes | Fail | None | Fix wording | Correct: 1,463,862.76 vs 1,455,850 budget. No currency given. |
| 80 | `uc-091-jml` | Priya Nair | Which access to give or remove | Yes | Yes | Pass | None | Pass | Correct: two with no approver, three unused for 90+ days. |
| 81 | `uc-092-accessrev` | Priya Nair | Which access to remove | Yes | Yes | Pass | None | Pass | Same text as uc-091; also lists no-approver items not asked for. |
| 82 | `uc-093-onbmgr` | Grace Ong | Whether every document and feed is in place before the first call | Yes | Yes | Pass | None | Pass | Correct: 3 of 5 done; call-back and statement schedule missing. |
| 83 | `uc-094-onbbank` | Daniel Foo | Whether the account and its signatories are approved | No | No | Fail | None | Fail | Lists two signatories; expected Daniel Foo missing. '(synthetic)' tag; 'Head of Finance: accounts 1' makes no sense; 'pending' not explained. |
| 84 | `uc-095-sopreview` | Priya Nair | Which procedures to review | No | No | Fail | None | Fail | One line only; 'due 0' is a broken value. Three overdue SOPs missing. |
| 85 | `uc-096-automation` | Anita Rao | Which process to automate | No | No | Fail | None | Fail | Heading and 'score 1,935' with no explanation. Expected figures and process names missing. |
| 86 | `uc-097-kycrefresh` | Tom Hale | Which documents to refresh before the bank or manager freezes the account | No | No | Pass | None | Fail | Answers the account 4471 question, not KYC documents. Expected dates (12 Sep 2026, 14 Nov, 2 Dec 2026, 5 Jan 2027) and owner Daniel Foo missing. |
| 87 | `uc-098-wordlist` | Anita Rao | Whether to add a word to the language list | Yes | Yes | Pass | None | Pass | Correct: add side letter and stub period; two already listed. |
| 88 | `uc-099-newfeed` | Anita Rao | Is the new feed designed, mapped and safe to go live? (build stopped) | No | No | Fail | gold_ build name and type error text shown to the user | Fail | No answer: the build stopped on a type error. Internal names shown. |
| 89 | `uc-100-famaccess` | Priya Nair | What each family member may see | Partly | Yes | Fail | None | Partial | Most access right. Wen Chen's Entity B line shows both 'none' and 'full'; stray '1' values. |
| 90 | `uc1-why-nav-moved` | Raj Patel | Why did Fund A move since the issued September report? | Yes | Partly | Pass | None | Partial | Gives the change (+180,000), not the reason (valuation amended after the report). 'Fund A' not tied to a fund name. |
| 91 | `uc10-pipeline` | Anita Rao | What was the Evergreen Liquid portfolio worth at 30 September 2026? | Yes | Yes | Pass | None | Pass | Correct: 41,200,000 USD. |
| 92 | `uc2-recon-break-desk` | Grace Ong | Which entity has a cash break on 8 October and by how much? | Yes | Yes | Fail | None | Fix wording | Correct break: Entity B 12,400 over the 5,000 tolerance. The 'Agree' list is garbled and repeats names. |
| 93 | `uc3-statements-inbox` | Helen Foo | Which statement is missing and how overdue is it? | Yes | Yes | Pass | None | Pass | Correct: Cedarpoint Opportunities II, 65 business days overdue. |
| 94 | `uc4-vs-benchmark` | Raj Patel | How did the liquid portfolio do against the benchmark in September 2026? | Yes | Yes | Pass | None | Pass | Correct: 4.17% vs 2.71%. Four-decimal figures and no 'ahead' word. |
| 95 | `uc5-limits` | Tom Hale | Which holding is over its single-name limit? | Yes | Yes | Pass | None | Pass | Correct: Harborview 5.75% vs 5%. Conflicts with uc-047 and uc-067 (seven names over 5%). |
| 96 | `uc6-liquidity` | Daniel Foo | What is our cash by entity today? | Partly | Yes | Fail | None | Partial | Right lines but no USD totals; SGD and USD mixed per entity, so the answer does not say how much cash each entity has. |
| 97 | `uc6-uncalled` | Daniel Foo | How much is uncalled across all commitments? | No | No | Pass | None | Fail | Repeats the uc-002 call answer. The uncalled total (14,600,000) is absent. Checker passes anyway. |
| 98 | `uc7-manager-diligence` | Sofia Reyes | What changed at Kestrel Ridge since the last meeting? | Yes | Yes | Pass | None | Pass | Correct: July value revised down 37,500. Does not mention the late statement from the same manager family. |
| 99 | `uc8-trades-vs-admin` | Sam Lee | How much does the FX forward confirmation differ from our record, and which October trades does the administrator not match? | Yes | Yes | Pass | None | Pass | Correct: 8,100 FX gap and three unmatched trades. One unmatched trade is from June, outside the October question. |
| 100 | `uc9-sop` | Priya Nair | What are the steps of the month-end report process and who does each one? | No | No | Fail | None | Fail | Wrong answer: returns the allocation band and performance text, not the month-end steps. Expected steps absent. |

## 3. Quality issues by kind

### 3.1 Wrong or missing answer (24)

Answers a different question, or none at all: `uc-005-benefcheck`, `uc-015-allowances`, `uc-032-driftrep`, `uc-039-irr`, `uc-041-commitappr`, `uc-043-liquidpnl`, `uc-046-attrib`, `uc-048-policyupd`, `uc-052-insurance`, `uc-055-corpact`, `uc-057-pricecheck`, `uc-062-fxlife`, `uc-071-expdist`, `uc-072-cashfc`, `uc-074-boardpack`, `uc-075-yearwalk`, `uc-078-redemption`, `uc-094-onbbank`, `uc-095-sopreview`, `uc-096-automation`, `uc-097-kycrefresh`, `uc-099-newfeed`, `uc6-uncalled`, `uc9-sop`.

Examples: `uc-072-cashfc` answers the allowances question (the example you flagged). `uc9-sop` returns the allocation band instead of the SOP steps. `uc-097-kycrefresh` answers the account 4471 question instead of KYC documents. `uc-078-redemption` gives cash by entity, not notice dates. `uc6-uncalled` repeats the call-7 answer; the uncalled total (14,600,000) is missing. `uc-032-driftrep` lists the asset classes inside their band when asked which are outside.

### 3.2 Partial answers (34)

Right figures, but no verdict or a missing part of the question: `morning-networth-note`, `uc-006-fxneed`, `uc-007-pacing`, `uc-010-bankexp`, `uc-016-schemadrift`, `uc-017-liab`, `uc-022-amendlog`, `uc-026-stmtadmin`, `uc-029-closeck`, `uc-030-vendors`, `uc-031-alloc`, `uc-033-breachesc`, `uc-034-prospect`, `uc-038-navroll`, `uc-040-icmemo`, `uc-044-twr`, `uc-047-icpack`, `uc-049-feedrag`, `uc-053-watchlist`, `uc-054-ladder`, `uc-059-breakage`, `uc-063-cashcode`, `uc-064-fxexp`, `uc-067-unrl`, `uc-069-lookthru`, `uc-073-runway`, `uc-076-scorecard`, `uc-080-vintage`, `uc-085-grants`, `uc-088-estateliq`, `uc-089-expapp`, `uc-100-famaccess`, `uc1-why-nav-moved`, `uc6-liquidity`.

Most common gap: the question asks for a decision (keep, approve, waive, recommend) and the answer gives the figures without the call.

### 3.3 Plain-words failures (46)

- Internal names, IDs or status labels: 14 builds.
- Missing or wrong currency or units: 10 builds.
- Synthetic test tags shown to the user: 5 builds.
- Garbled, repeated or unreadable text: 19 builds.

Rewrites (one line each, how the answer should read):

- `morning-networth-note`: The September 2026 office report puts the family at USD 57.6 million (scope to confirm). In SGD that is about 77.3 million.
- `uc-004-callcheck`: No. Holdings has USD 1,230,000 against the USD 1,250,000 call due 23 Oct and the USD 250,000 buffer, so it is USD 270,000 short. Converting SGD 361,800 (of its SGD 1,600,000, worth USD 1,194,029.85) at USD/SGD 1.34 covers the gap.
- `uc-005-benefcheck`: Not confirmed. The call notice gives account ending 4471; the standing instruction on file ends 2209. The payment is held until Grace calls Cedarpoint on the number in the April subscription pack and records the call-back.
- `uc-006-fxneed`: Convert SGD 361,800 at about 1.34 to cover the USD 270,000 shortfall. The bank's confirmation (rate 1.3405, SGD 361,935, from the spec's answer key; check the PDF) is within 0.1% of plan, so the trade is in line.
- `uc-008-payrun`: Release Harbourline Fund Services USD 16,234.50 and Summit Tax Advisory SGD 5,400. Hold Anchorage Custody USD 6,180 (1,030 above the fee schedule) and Cedarpoint Ventures III USD 1,250,000 (approval not given; account changed, no call-back).
- `uc-010-bankexp`: 84% of cash (USD 5.17m of 6.16m) sits at Harbour Bank. The policy sets no bank limit, so there is no breach to report until one is set.
- `uc-016-schemadrift`: One column changed name in the administrator's positions file: 'Market Value' is now 'Valuation Amount (USD)'. It still feeds the same market-value figure, so the load can continue once Anita confirms the match.
- `uc-018-fundplan`: Evergreen Holdings is USD 270,000 short for the USD 1,250,000 call due 23 Oct. Entity B has USD 618,343.96 above its buffer and can transfer it first. Evergreen Family Trust is USD 36,104.48 short after its buffer, so it cannot help.
- `uc-026-stmtadmin`: Ask the administrator to correct the three final statements: Evergreen Growth II (670,000 apart), Saltmarsh Infrastructure Fund II (350,000) and Evergreen Credit III (330,000). The three estimates can wait for final figures.
- `uc-031-alloc`: Listed equity 36.37%, private equity 15.76%, hedge funds 11.36%, and the rest in smaller classes (list them). By entity: Evergreen Family Trust 58.90%, Evergreen Holdings 25.03%, Entity B 16.07%. Total USD 108,230,000.
- `uc-032-driftrep`: None are outside their band. Listed equity 80.61% (band 60 to 90%), hedge funds 54.55% (band 20 to 60%), and the Cedarpoint Ventures line 26.73% (band 0 to 55%; a fund name, so confirm its asset class).
- `uc-038-navroll`: Not fully. Evergreen Growth I at 30 Sep: 9,265,520 opening, less 262,500 distributions, plus 1,189,480 gain, gives 10,192,500, which is 12,500 more than the reported 10,180,000. No calls in the quarter.
- `uc-039-irr`: Two funds are ahead on both measures: Evergreen Credit III (17.28%, 1.13x) and Evergreen Growth II (9.83%, 1.28x). Saltmarsh Renewables I is below cost on both. Five funds show IRR and multiple disagreeing, so their figures need checking before any decision.
- `uc-041-commitappr`: Not yet. No private markets budget is set, so the budget test cannot run. The USD 2,000,000 ticket takes uncalled commitments to USD 16,600,000. If all of that were called within 24 months (an assumption, not a signed pacing rule), cash of USD 6,156,041.41 would be short.
- `uc-043-liquidpnl`: Today the liquid book is down USD 11,100 on Evergreen Liquid portfolio only; 7 of 8 portfolios are not loaded yet, so the month-to-date figure is not available.
- `uc-046-attrib`: The bond side cost most: selection -0.10% and allocation -0.05%. Listed equity cost a further -0.03% on allocation. Change bond selection first. The stated total (-0.12%) does not match the parts (-0.17%), so check it before sending.
- `uc-047-icpack`: For committee: September performance (liquid book 4.17% vs benchmark 2.71%) and attribution are ready; one report line is still an estimate. Breaches: Harborview Semiconductor at 5.75% against 5%, plus other open breaches (count to confirm). Proposals: USD 1,250,000 Cedarpoint call due 23 Oct, and USD 13 million of deals in review, including the USD 2,000,000 Harborlight ticket.
- `uc-048-policyupd`: No limit change is proposed on this evidence: the signed single-name limit is 5%. The four largest single names are 6.13%, 5.89%, 5.74% and 5.71%, all above 5%; list them by name.
- `uc-052-insurance`: Two policies expire within 60 days: Umbrella liability (POL-LIAB-03), cover USD 10,000,000, and Family office cyber (POL-CYB-04), cover USD 1,000,000. Expiry dates are 1 Nov and 1 Dec 2026 (confirm which is which). Fine art and Bayview cover to be confirmed.
- `uc-055-corpact`: No answer yet: the corporate-actions calendar did not finish building because a missing value was read as a number. Fix the value type before it goes to ops.
- `uc-057-pricecheck`: Two prices are outside tolerance: Kingfisher Telecom shares (-1.86%) and the Kingfisher Telecom 4.6% 2030 bond (+0.81%), both against the fund administrator. The tolerance figure is not stated in the answer; add it.
- `uc-058-settle`: Two trades have not settled: Evermore Banking Group buy of USD 312,000 (due 9 Oct, 3 days late, instruction mismatch) and Larkspur Health buy of USD 281,150 (due 6 Oct, 6 days late, seller short delivery). Chase Broker Two for both.
- `uc-060-docinbox`: IMG_2210.pdf looks like a restaurant bill, not a finance file: refuse and return to the sender. data_export.xlsx has columns we do not recognise (Ref, Amt1, Amt2, Flag): hold and ask the sender. scan_0412.pdf duplicates a notice already loaded: no action. account_extract.xlsx duplicates a bank statement already loaded: no action.
- `uc-061-dqscore`: Fix the administrator cash file first: it scores 71.4%, with 5 of 7 loads on time and clean. Next are custodian transactions and administrator NAV (85.7% each).
- `uc-063-cashcode`: Three bank lines have no purpose, net USD 42,120: 19 Aug USD 48,250 received from an unnamed remitter (Evergreen Holdings); 23 Sep USD 3,980 card debit to an unnamed merchant (Evergreen Holdings); 6 Oct USD 2,150 cheque with no payee shown (Entity B).
- `uc-064-fxexp`: SGD exposure after forwards is USD 8.85 million, 7.62% of the family's USD 116.1 million; USD exposure is 92.38%. Whether to hedge more is for the CFO.
- `uc-065-realassets`: Six real assets worth USD 17,990,298.50. Evergreen Holdings holds USD 10,764,179.10 (Bayview residence, fine art, yacht). Evergreen Family Trust holds USD 5,426,119.40 (Hillcrest House, wine collection). Entity B holds USD 1,800,000 (Coastal land parcel), but its title is in Lin Chen's name.
- `uc-067-unrl`: For tax, sell the loss lots first: LOT-AHS-2 (Atlas Harbour Shipping, loss 159,480), then LOT-SPS-1 (144,650) and LOT-TWE-1 (144,640). For the 5% limit, Harborview Semiconductor needs USD 324,210.53 sold; six other names are over 5% on this view (confirm, since the allocation report shows one breach).
- `uc-068-incomef`: Income to plan for, 13 Oct 2026 to 13 Oct 2027: USD 811,406.60, made up of USD 362,000 coupons and USD 449,406.60 dividends, from 54 payments.
- `uc-071-expdist`: No forecast yet: there is no distribution schedule for the funds on file, so the cash expected back over the next year is not shown. Ask the fund administrators for their distribution schedules.
- `uc-074-boardpack`: Board headlines, 30 Sep 2026: net worth USD 57.6 million (the Growth I valuation is an estimate in the issued report). Liquid book +4.17% in September vs 2.71% benchmark; Q3 3.51% vs 5.01%. Cash USD 6.16 million. Unfunded commitments USD 14.6 million. One cash shortfall: USD 270,000 for the 23 Oct Cedarpoint call.
- `uc-075-yearwalk`: No answer yet: the year-to-date worth summary did not build (a syntax error in the summary step). It needs a fix before it goes to the family.
- `uc-076-scorecard`: Add: Bluewater Capital (score 98.3; return 14.7%; on time; no watch flags) and Northgate Partners (91.8; return 10.7%; one watch flag). Keep: Meridian Index Managers (50; return -3.5%). Review or exit: Kestrel Ridge Advisors (45.4; 93% of statements on time), Cedarpoint Ventures (35; return -19.1%), Saltmarsh Real Assets (27; 60% on time).
- `uc-079-rebalance`: Proposed, not signed: buy about USD 4.82 million of bonds (18.6% to the 30% target) and USD 0.99 million of convertibles (2.65% to 5%); sell USD 5.81 million of listed equity (78.75% to 65%).
- `uc-084-taxest`: Set aside USD 159,156.51 in total (currency assumed): Entity B 15,242.98, Evergreen Holdings 29,054.88, Evergreen Family Trust 114,858.65. Entity B's figure is low because one month of its bank statements has not arrived, so tax on that interest is missing.
- `uc-085-grants`: Not this one: REQ-2026-06 (USD 50,000 to Seabird Sanctuary Trust) would take the grant budget past the 35,000 left (265,000 of 300,000 used, 88.3%). Paying it would leave cash 70,000 short of the calls due in 30 days, before the 250,000 buffer. The charity is 19 months old against a 24-month rule.
- `uc-086-grantappr`: Not yet: REQ-2026-06 (USD 50,000 to Seabird Sanctuary Trust) is more than the USD 35,000 left in the grant budget, paying it leaves cash 70,000 short of calls due in 30 days, and the charity is 19 months old against a 24-month rule.
- `uc-090-offcost`: Yes, slightly: office costs USD 1,463,862.76 against a budget of USD 1,455,850 (8,013 over; currency assumed USD). Professional fees are 35,752 over and grants 25,000 over.
- `uc-094-onbbank`: Not approved. The new EUR account at Tidewater Commercial Bank for Evergreen Family Trust is pending, with Raj Patel and Grace Ong as signatories. The signing policy also needs Daniel Foo, who is not yet on it.
- `uc-095-sopreview`: Review now: the quarterly access review (owner Priya Nair, overdue; the data shows 0 days, which needs fixing), and three SOPs not reviewed for 378 to 681 days: open or change a bank account, vendor payment run, payroll release.
- `uc-096-automation`: Automate the bank statement chase first: about 2,040 minutes a month of manual work (pairing per the check list; confirm), with 1,395 minutes for chasing late or missing files. Collecting manager statements is next (ranking score 1,935).
- `uc-099-newfeed`: No answer yet: the new custodian feed did not finish its mapping check (a text value was compared with a number). Fix before it goes live.
- `uc-100-famaccess`: Lin Chen: full access to Evergreen Holdings and Evergreen Family Trust; none to Entity B. Maya Chen and Ethan Chen: summary of Evergreen Family Trust; none of the other two entities. Wen Chen: summary of Evergreen Family Trust, none of Evergreen Holdings; Entity B shows both 'none' and 'full', which needs fixing.
- `uc2-recon-break-desk`: Entity B has a cash break of USD 12,400 on 8 October, above the USD 5,000 tolerance. The other entities are within tolerance.
- `uc6-liquidity`: Cash today in USD at 1.34: Evergreen Holdings 2.42m (USD 1.23m plus SGD 1.6m); Entity B 1.80m (USD 0.87m plus SGD 1.25m); Evergreen Family Trust 1.93m (USD 0.21m plus SGD 2.30m). Total 6.16m.
- `uc9-sop`: Steps not returned. The answer should list each month-end step with its owner, system and check, taken from the process narrative.

### 3.4 Leaks (4)

- `uc-041-commitappr`: 'the assumption of the answer key' is test wording in a family answer.
- `uc-055-corpact`, `uc-075-yearwalk`, `uc-099-newfeed`: the stuck message shows internal build names (`gold_...`) and error text.
- Names: as far as checked, every counterparty and person is from the synthetic Evergreen universe. Several start with 'Harbour' or 'Harborview' (for example Harbour Bank, Harborview Semiconductor). These are fixture names, not the product name, but they sit close to 'Signal Harbor', so consider renaming them in the fixture.
- Data handling: `uc-060-docinbox` quotes the content of an unrecognised file (a restaurant bill with table and guest count). Not a leak of a real person, but the answer should say what the file is, not quote it.

### 3.5 Contradictions

Inside one answer:
- `uc-039-irr`: IRR and TVPI point opposite ways for 5 of 8 funds (Evergreen Income II 32.74% with 0.92x; Cedarpoint Ventures III -40.54% with 1.38x).
- `uc-046-attrib`: Components sum to -0.169%; the stated total is -0.1169%.
- `uc-044-twr`: YTD, last 12 months and all months show identical figures (3.821% and 5.7563%).
- `uc-038-navroll`: Arithmetic is right (12,500 gap) but the sentence says 'not explained by -12,500'.
- `uc-085-grants`: 'Leaving -70,000' only works after paying the 50,000 grant; the text does not say so.
- `uc-100-famaccess`: Wen Chen's Entity B line shows both 'none' and 'full'.
- `uc-054-ladder`: 'Cash after' ignores the 250,000 buffer that uc-004 and uc-070 apply.
- `uc-088-estateliq`: Liquid assets behind the 2.95x cover (55,879,741.41) cannot be traced; liquid book plus cash less debt is about 45.6m.

Between answers (the family would ask which is right):
- `uc-001-noticelog`: 5,950,000 of earlier calls paid, vs 6,000,000 called before call 7 in uc-002.
- `morning-networth-note`: Family total 57.6m, vs 105.4m after debt (uc-017), 116.1m (uc-064), 131.3m estate (uc-088).
- `uc-017-liab`: Total 105.4m after debt; uc-031 says 108.2m before debt; uc-064 says 116.1m.
- `uc-047-icpack`: Says 7 real breaches; uc5 and uc-033 say one (Harborview).
- `uc-067-unrl`: Says 7 names over 5% in the liquid book; uc5 and uc-033 say one.
- `uc-053-watchlist`: Window starts 16 Jul; the check expects 15 Jul.

The family total is the biggest of these: the same question gives 57.6m, 105.4m, 108.2m, 116.1m and 131.3m depending on the build.

### 3.6 Checker false passes (14)

The checker says pass, but expected values are missing from the answer text: `uc-005-benefcheck`, `uc-007-pacing`, `uc-029-closeck`, `uc-031-alloc`, `uc-037-distrack`, `uc-038-navroll`, `uc-044-twr`, `uc-045-reportpack`, `uc-046-attrib`, `uc-049-feedrag`, `uc-057-pricecheck`, `uc-063-cashcode`, `uc-091-jml`, `uc6-uncalled`.

Format-only differences (for example '2026-08-05' against '5 Aug 2026') were not counted.

## 4. Ten worst answers

1. `uc9-sop` (Priya Nair): Wrong answer: returns the allocation band and performance text, not the month-end steps. Expected steps absent.
2. `uc-072-cashfc` (Daniel Foo): Answers the allowances question (September owed to Ethan Chen) instead of the 12-month cash forecast. Checker fails.
3. `uc-097-kycrefresh` (Tom Hale): Answers the account 4471 question, not KYC documents. Expected dates (12 Sep 2026, 14 Nov, 2 Dec 2026, 5 Jan 2027) and owner Daniel Foo missing.
4. `uc-078-redemption` (Grace Ong): Answers cash by entity, not the notice deadline or the payment date. Checker fails on all dates and amounts.
5. `uc-005-benefcheck` (Grace Ong): Does not answer whether the account is genuine. Gives no 2209 (the account on file). Shows a net-worth list instead. Checker passes only because 4471 appears.
6. `uc-032-driftrep` (Tom Hale): Lists the asset classes INSIDE their band; the question asks which are OUTSIDE. Underscored names; a fund name is shown as an asset class.
7. `uc-043-liquidpnl` (Raj Patel): Gives one day's P&L (-11,100) for 1 of 8 portfolios, not month to date. '1 portfolios loaded (of 8)'. Expected 42,273,700 and 1,084,800 absent.
8. `uc-052-insurance` (Priya Nair): Values read USD 0, SGD 0, SGD 1, USD 1 (units wrong). No expiry dates. Two extra policies listed. 'None' shown for linked asset.
9. `uc-041-commitappr` (Raj Patel): Garbled. No verdict on budget, limit or cash. 'short' has no amount. Expected 2,000,000, 16,600,000 and 37.08 are absent.
10. `uc-074-boardpack` (Mei Chen): Headline figures missing (77,253,120; 3.5148; 5.7563; cash; 270,000; 14.6m). Lists labels with no figures; '2026Q3 in September 2026' contradicts itself; 'estimated' given with no reason.

## 5. Caveats

- The 300,000 and 265,000 grant budget figures, the 681/480/378 day counts and the 2,040 and 1,395 minute pairings in the rewrites come from the check's expected values, not from the answers. Confirm before use.
- Currency is assumed to be USD where the answer gives none; that is flagged, not corrected in the data.
- This is a read of the answers as text and of their internal arithmetic. It does not re-run the data.
