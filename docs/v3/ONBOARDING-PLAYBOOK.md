# Onboarding playbook: the human side

This is the part of onboarding a person does. Harbor does the rest and shows it on Build > Onboarding, which lists the ten steps from PROGRAM-GAPS W8, who owns each, what Harbor did, and a health score out of 100. The target is 2 to 4 weeks from the first call to go-live. The slow step is almost always the authorisation letters, so start them on day one.

## Who does what

| Role | Does |
|---|---|
| Office admin (client) | Signs the authorisation letters, names the people, ticks go-live. |
| Head of data (ours) | Owns the plan, runs the connectors, checks the opening balances, signs the model. |
| Data team (ours) | Drops the history, works the review queue, helps with ownership. |
| Sponsor (client) | Agrees the reports wanted and the go-live date. |

## The ten steps

1. **Discovery (week 1, day 1 to 3).** One call of about 90 minutes with the office admin and the sponsor. Collect: the entities and their ownership chart, every bank and custodian account, the funds, and the five reports the sponsor looks at first. Harbor drafts the brief from the call. Check the brief with the office admin before moving on.
2. **Authorisation letters (start day 1, takes weeks).** Each bank and custodian needs a signed letter from the client allowing them to send us data. Send the template for every institution in one batch. Keep a list: institution, date sent, date signed, date first file. Nobody on our side holds the client's online banking login. Tick the step when every letter is signed, and chase any institution quiet for 5 working days. While waiting, use files the client already receives (statements by email or in a folder), which need no letter.
3. **Historical load (week 1 to 2).** Ask for at least 6 months of statements and transactions, 24 months if they have them. Drop them in the drop folder as they come. Harbor reads them, with receipts. Work the review queue as it fills. Do not wait for everything to arrive before starting.
4. **Opening balance reconciliation (week 2).** Our figures must equal the custodian's and the administrator's on day one. Harbor runs the cash recon. For each difference, find the cause (timing, a missing file, a wrong mapping), fix it and re-run. The step is done only when the recon shows no differences, or each one is explained and signed by the head of data.
5. **Ownership structure (week 2).** Confirm the chart from discovery against the legal documents. Harbor builds the ownership table; the head of data checks percentages add up per entity and that no entity is missing a parent. Ask the client to confirm the chart in writing.
6. **Reports and dashboards (week 2 to 3).** Build the five reports from discovery. Show each with its receipts. Agree with the sponsor what "right" looks like for each before showing the whole office.
7. **User testing (week 3).** Two or three office staff use the system for their real morning routine for a week. Collect every "I did not understand this" and every number they distrust. Fix, then ask them to try again. Tick when they say they would use it.
8. **Training (week 3).** One 60-minute session per role, in the client's own words and with their own data. Leave a one-page guide per role. Tick with the number of people trained.
9. **Go-live (week 3 to 4).** Agree the date with the sponsor. Check the day before: feeds connected, review queue empty, health score above 85. The office admin ticks go-live.
10. **Hypercare (first 2 to 4 weeks after go-live).** A 15-minute check-in every morning: what came in, what is in the queue, what looks wrong. Drop to twice a week when two clean weeks pass. Then hand over to normal data operations: daily recon, the exception queue, assets with no feed, chasing missing statements.

## The health score

Out of 100: feeds connected 25, history loaded 25 (6 months is full marks), opening balances reconciled 25, review queue empty 15, ownership set 10. Aim for above 85 at go-live. A low score tells you where to look first, and each line says why.

## Ticking steps

The steps only a person can do (letters, user testing, training, go-live, hypercare) are ticked on the page by the office admin, head of data, sponsor or data team. The tick records name and time. Add what was done, for example "Two sessions, nine people", so the record is useful later. A tick can be removed if it was made by mistake.

## Rules of thumb

- Never ask a client for a password, key or token in an email or chat. Settings go into the server's environment, set by the person who owns the account.
- Real client data stays in the client's environment. Use synthetic data for demos.
- Anything that moves money is held until a person confirms the bank details on a known number.
