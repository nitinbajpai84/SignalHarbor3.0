# Team of ten: who does what, what Harbor suggests they build, and how we check it

Source of truth: `packs/family_office/1/role_builds.yaml` (industry suggestions, never enforced; the person decides). Contract: `docs/v3/TEAM-BRIEF.md`.
Skill ids are from `docs/v3/SKILLS-CATALOGUE.md`. Every number in "How we check" is copied from `docs/test/10UC-ANSWER-KEY.md` or `docs/demo/uc6/ANSWER-KEY.md`.
Files are folders (or globs) under `tests/v1/fixtures/10uc`, or `uc6:<month>` = `docs/demo/uc6/sources/<month>`.

## The matrix

| Person | Title | Actions | Suggested builds | Skills | Files | Dashboard | How we check (ask / expect) |
|---|---|---|---|---|---|---|---|
| Raj Patel (`cio`) | Chief Investment Officer | - Read why the NAV or the P&L moved since the report we issued<br>- Decide whether a manager revision needs the committee<br>- Compare the portfolio with its benchmark each month<br>- Sign off the monthly investment report | **uc1-why-nav-moved** Why did the NAV move since the issued report? | `intent.restate-ask`, `data.recognise-file`, `data.read-pdf-fields`, `check.against-source`, `check.explain-difference`, `consume.answer-question` | `issued_reports/*2026-09*`<br>`admin_exports/administrator_export_2026-09.xlsx`<br>`emails/04_revision_notice_A_2026-09-30_amended.eml`<br>`manager_statements/northgate_A_2026-09-30_*` | Consume: issued versus known now, NAV bridge by portfolio | Ask: Why did Fund A move since the issued September report?<br>Expect: `10,180,000`, `180,000` |
|  |  |  | **uc4-vs-benchmark** How did the portfolio do against its benchmark? | `intent.define-figure`, `data.recognise-file`, `build.write-formula-table`, `check.adds-up`, `consume.attribution`, `consume.answer-question` | `benchmark_workbook`<br>`market_data`<br>`admin_exports/administrator_export_2026-08.xlsx`<br>`admin_exports/administrator_export_2026-09.xlsx` | Consume: portfolio against benchmark, by month | Ask: How did the liquid portfolio do against the benchmark in September 2026?<br>Expect: `4.1667`, `2.7072` |
| Daniel Foo (`cfo`) | Head of Finance | - Approve funding for a capital call<br>- Check each entity has cash for the calls due in 30 and 60 days<br>- Move cash between entities when one is short<br>- Confirm a call notice against the commitment before it is paid<br>- Report uncalled commitments to the principal | **uc6-liquidity** Can each entity meet its capital calls? | `intent.restate-ask`, `data.recognise-file`, `data.match-identity`, `check.against-source`, `action.detect-exception`, `consume.answer-question` | `uc6:2026-07` | Consume: cash by entity and calls due | Ask: What is our cash by entity today?<br>Expect: `2,305,906.48`, `1,252,492.34`, `905,000` |
|  |  |  | **uc6-uncalled** How much of our commitments is still uncalled? | `data.recognise-file`, `check.adds-up`, `consume.understand-words`, `consume.answer-question` | `uc6:2026-07` | Consume: commitments, called and uncalled by fund | Ask: How much is uncalled across all commitments?<br>Expect: `13,450,000` |
| Anita Rao (`head_of_data`) | Head of Data | - Approve the design of a new data pipeline<br>- Check that every figure on a board traces to a file<br>- Decide what happens when a file arrives with a new column<br>- Keep the model and the office's words in step | **uc10-pipeline** A monthly pipeline and insight from the administrator and trading files | `data.profile-file`, `model.find-reusable`, `model.design-ready-table`, `map.map-file`, `build.write-ready-sql`, `run.on-copy`, `check.adds-up`, `consume.build-board` | `admin_exports`<br>`trading_export/trading_export_2026100*.csv` | Consume: net worth by portfolio, where is this from | Ask: What was the Evergreen Liquid portfolio worth at 30 September 2026?<br>Expect: `41,200,000` |
| Mei Chen (`principal`) | Principal | - Read how much the family is worth this morning<br>- Ask a plain question and get a plain answer with its source<br>- Decide what to tell the board of the family<br>- Be told when something needs her decision | **morning-networth-note** A morning note on what we are worth | `intent.restate-ask`, `data.recognise-file`, `build.write-formula-table`, `consume.write-morning-note`, `consume.explain-number` | `issued_reports/*2026-09*`<br>`market_data/fx_usdsgd_wmr4pm.csv` | Consume: the morning note, net worth in USD and SGD | Ask: What are we worth in the latest report?<br>Expect: `57,600,000` |
| Sofia Reyes (`investment_analyst`) | Investment Analyst | - Prepare for a manager meeting<br>- See what changed at a manager since the last meeting<br>- Read newsletters and statements for team or process changes<br>- Write up a view for the investment committee | **uc7-manager-diligence** What changed at Kestrel Ridge since we last met? | `intent.read-company-doc`, `data.read-pdf-fields`, `data.match-identity`, `check.against-source`, `consume.answer-question` | `research_docs`<br>`notes/04_kestrel_ridge_onsite_2026-06-12.md`<br>`manager_statements/kestrel_H1_2026-0[7-9]*` | Consume: manager timeline, what changed since the last meeting | Ask: What changed at Kestrel Ridge since the last meeting?<br>Expect: `7,012,500` |
| Grace Ong (`ops_lead`) | Operations Lead | - Run the daily cash reconciliation<br>- Look at each break and decide timing or error<br>- Chase the administrator or the bank for a missing item<br>- Close a break with its reason<br>- Hand the unresolved ones to Finance | **uc2-recon-break-desk** Daily cash reconciliation and break desk | `data.recognise-file`, `data.match-identity`, `check.against-source`, `action.detect-exception`, `check.explain-difference`, `action.route-owner` | `uc6:2026-10/administrator_cash_2026-10.csv`<br>`bank_cash`<br>`trading_export/cash_movements_trading_export_2026-09-09_to_2026-10-08.csv` | Consume: cash differences by entity, open breaks | Ask: Which entity has a cash break on 8 October and by how much?<br>Expect: `12,400` |
| Helen Foo (`fund_accountant`) | Fund Accountant | - Track which manager statements are expected and which arrived<br>- Flag late and missing statements<br>- Draft the follow-up to a manager<br>- Log amended statements and what they replace | **uc3-statements-inbox** Manager statements: expected against received, and late | `data.recognise-file`, `data.read-pdf-fields`, `data.match-identity`, `action.detect-exception`, `action.draft-message`, `consume.answer-question` | `emails`<br>`manager_statements/*_2026-0[6-9]-*` | Consume: statements expected against received, late and missing | Ask: Which statement is missing and how overdue is it?<br>Expect: `63` |
| Tom Hale (`risk_officer`) | Risk and Compliance Officer | - Check holdings against the signed allocation limits<br>- Look into a breach and say whether it is real or caused by stale data<br>- Tell the investment committee about a real breach<br>- Keep the allocation policy and its limits up to date | **uc5-limits** Allocation and limit monitoring | `intent.read-company-doc`, `data.recognise-file`, `build.write-formula-table`, `action.detect-exception`, `action.size-impact`, `check.explain-difference` | `policy`<br>`admin_exports/administrator_export_2026-09.xlsx`<br>`security_master` | Consume: holdings against limits, breaches open | Ask: Which holding is over its single-name limit?<br>Expect: `5.75` |
| Priya Nair (`hr_admin`) | Office and HR Manager | - Write down how a routine process works today<br>- Turn a process into a standard operating procedure<br>- Onboard a new joiner and give access<br>- Keep expense approval and sign-off rules current | **uc9-sop** Process map and SOP for the month-end report | `intent.read-company-doc`, `intent.draw-process-lanes`, `intent.draw-process-steps`, `intent.map-decision-path`, `intent.write-sop` | `process_narrative` | Consume: the process map and the SOP, steps flagged for automation | Ask: What are the steps of the month-end report process and who does each one?<br>Expect: none (the SOP / process map exists and the answer names the steps) |
| Sam Lee (`ops_clerk`) | Operations Clerk | - Match each trade against the administrator's booking<br>- Check the FX forward confirmations against our own record<br>- Raise a break when quantity, price or amount differ<br>- Send the unmatched trades to the Operations Lead | **uc8-trades-vs-admin** Trades and FX forwards against the administrator and the confirmations | `data.recognise-file`, `data.read-pdf-fields`, `check.against-source`, `action.detect-exception`, `check.explain-difference`, `action.route-owner` | `trading_export/trading_export_2026100*.csv`<br>`trading_export/trading_export_20260915.csv`<br>`otc_confirms`<br>`admin_exports/administrator_export_2026-09.xlsx` | Consume: trades and confirmations matched, breaks open | Ask: How much does the FX forward confirmation differ from our record?<br>Expect: `8,100` |

## What each person says (the first message of the build)

- **Raj Patel** (Chief Investment Officer, build `uc1-why-nav-moved`): "Every month I want to know why our number moved between the report we issued and what we know now. Fund A sent an amended September statement, so show me what changed and by how much, and who needs to look at it. I read it, Mei checks it."
- **Raj Patel** (Chief Investment Officer, build `uc4-vs-benchmark`): "I need to see how the Evergreen Liquid portfolio did last month against our blended benchmark, in one line I can put in front of the committee. The benchmark definition is in the workbook, the index levels are in the market data."
- **Daniel Foo** (Head of Finance, build `uc6-liquidity`): "I want to know every morning whether each entity can meet its capital calls from cash: cash by entity, calls due in 30 and 60 days, and uncalled commitments. Mei and Raj read it; I decide. Monthly refresh."
- **Daniel Foo** (Head of Finance, build `uc6-uncalled`): "Show me, fund by fund, what we committed, what has been called and what is still to come, so I can plan the cash for the year."
- **Anita Rao** (Head of Data, build `uc10-pipeline`): "I want a monthly pipeline that takes the administrator's positions and the trading export, cleans them, and gives me net worth by portfolio on a board that shows where every number came from. The administrator file changed a column name once, so it has to cope with that."
- **Mei Chen** (Principal, build `morning-networth-note`): "Each morning I would like a short note: what we are worth, in dollars and in Singapore dollars, what changed since last time, and anything that needs me. Plain words, no jargon, one page."
- **Sofia Reyes** (Investment Analyst, build `uc7-manager-diligence`): "Before I see Kestrel Ridge again I want one page of what changed since our last meeting on 12 June: statements, restatements, team changes in their newsletter. Newest first, each item with where it came from. No opinions, I'll bring those."
- **Grace Ong** (Operations Lead, build `uc2-recon-break-desk`): "Every morning I check cash for each entity: administrator against the bank and our trading desk. Anything over 5,000 I want as a break with the likely cause, and the ones that are just timing marked as timing. Entity B was off on the 8th, start there."
- **Helen Foo** (Fund Accountant, build `uc3-statements-inbox`): "For every fund I want to see the statement we expect each month against what has arrived, who is late and by how many days, and any that never came. For the missing one, draft me the chase email, I will send it myself."
- **Tom Hale** (Risk and Compliance Officer, build `uc5-limits`): "I want to test the liquid book against our signed limits every month: no single name over 5 percent, listed equity between 60 and 90. Tell me what is a real breach and what is just a stale or missing value, and anything that has no asset class."
- **Priya Nair** (Office and HR Manager, build `uc9-sop`): "We do the month-end investment report from memory and from Mei's email. I want the steps written down properly: who does what, in which system, what is checked, what happens when it goes wrong, and a procedure document I can hand a new joiner."
- **Sam Lee** (Operations Clerk, build `uc8-trades-vs-admin`): "Each day I match what our desk traded against what the administrator booked, and the FX forward confirmations against our own record. Show me what matches and what does not, by how much, and which ones I should send to Grace."

## Test protocol

One persona run proves three things for one person: they can **build** it (the thread reaches live), **do their work** (Harbor asks only what a person would be asked, the decisions are theirs), and **see it land** (the answer carries the answer-key numbers, and the desk, build page and consume board show it as that person).

**Make the office** (once per run group; a fresh root each time, never the repo `data/`):

```
sh docs/test/uc-live/uc6-scripts/py.sh v3_team_env.py D:/Temp/sh3-team-env                        # 10UC roles, company clock 2026-10-09
sh docs/test/uc-live/uc6-scripts/py.sh v3_team_env.py D:/Temp/sh3-team-env-uc6 --today 2026-07-31   # cfo (UC6 July) needs 2026-07-31
```
It makes the clean Evergreen office (master data only), adds Tom Hale, Priya Nair and Sam Lee, and writes `jobs` {email: role id} into `<root>/evergreen/v3/settings.json`.
Passwords stay in `<root>/_control/seed_credentials.txt`.

**Run one person** (background shell, 20+ minutes; never inside a reasoning-model agent):

```
UC6_BASE=http://127.0.0.1:<port> UC6_ENV=D:/Temp/sh3-team-env UC6_SHOTS=D:/Temp/sh3-team/shots/<role> UC6_TMP=D:/Temp/sh3-team/tmp-<role> \
  sh docs/test/uc-live/uc6-scripts/py.sh v3_persona.py <role_id> [--build 2]
```
Steps the script takes as that person: drop the build's files into `<env>/evergreen/dropbox`; start the thread with the build's `say`; wait out drafting; if Decision 1
shows gaps say "use the usual practice" once, then confirm; on a question event say "retry" once, then record **STUCK**; Decision 2 with the assumed answers and the
administrator or custodian file as the check; Decision 3 go live; then `POST /api/v3/ask` with `check.ask` and test that every `expect` value is in the answer
(commas and a trailing `.00` are ignored, nothing else is).

**Rules for the orchestrator**
- One persona per environment at a time. `/api/v3/ask` answers from the first live thread of the office, so two personas live in one root would read each other's data. Use one root (and one server) per persona, or run them one after the other.
- Give each persona its own `UC6_TMP` so the sign-in state and the call log do not mix. Do not use ports 8630 to 8632.
- The dropbox is shared inside a root: files from an earlier persona are still there. A fresh root per persona keeps the test honest.
- Resume: run the same command again; the state file `D:/Temp/sh3-team-<role>.json` carries the thread id and what was already said. Delete it to start over.

**Report** (`D:/Temp/sh3-team/<role>.json`, rewritten at every step): role, person, build, stage reached, `done`, `stuck_at`, the questions Harbor asked (count and texts),
seconds per stage, the answer text, the check (`ask`, `expect`, `missing`, `pass`) and the screenshot paths (desk, build page, consume board).

**Pass / fail**
- *Built*: `done` true (the thread reached live). A question that survives one "retry" is STUCK and is a finding, not a failure of the script.
- *Worked as the person*: the questions Harbor asked are things this person could answer in a sentence; none asks for a table, column or file format.
- *Landed*: `check.pass` true. For UC9 `expect` is empty, so the check is that the SOP or process map exists: the thread is live and the answer names the steps and who does them.
- The numbers come from the answer keys. If a number is wrong, fix Harbor, not the key; if the key does not apply to the dropped files, say so in the report and do not change the key.

## Notes and known edges

- Helen Foo (Fund Accountant) is already in the base seed as the family principal account (platform role `owner`); the persona run signs in as her. Tom Hale (`participant`), Priya Nair (`analyst`) and Sam Lee (`analyst`) are added by `v3_team_env.py`.
- The environment is the clean one: master data and commitments only, no ten-use-case history. Expected numbers were therefore chosen so the dropped files alone can give them
  (for example the UC8 check uses the FX confirmation against the trading export, 8,100 SGD; UC2 uses the Entity B wire of 12,400). The UC6 July build uses the proven folder `docs/demo/uc6/sources/2026-07`.
- The UC4 check expects the portfolio return 4.1667 and the blend 2.7072; the difference 1.4595 is in the key but is not asked for, because the answer may round it.
- UC9 has no fixture for onboarding or expense approval; the build uses the month-end process narrative (`process_narrative`).
