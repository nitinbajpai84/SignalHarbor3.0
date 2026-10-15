# Evergreen Office demo: ten-minute walkthrough

Evergreen Office is a fictional family office. All names and figures are invented.

## Set up
1. `python tools/seed_evergreen.py` makes the company, seven people and the history. Sign-in details are in `data/_control/seed_credentials.txt` (never printed). `--reset` rebuilds only the Evergreen warehouse.
2. `python tools/seed_e0_demo.py evergreen` drops the sample workbooks in the inbox. `python tools/make_e2_statements.py` makes the manager PDFs (when that tool is installed).

## People
Daniel Foo (CIO), Mei Chen (Operations), Raj Patel (Finance), Sofia Reyes (Risk), Anita Rao (head of data), Leo Park (data engineer), Grace Ong (company admin). Emails are `first.last.evergreen@example.test`.

## The story
1. **Monday, Daily Pulse (Mei).** Entity B cash: the administrator says 880,400 USD, the trading export says 868,000 USD on 8 Oct. The 12,400 USD gap is over the 5,000 USD tolerance, so a case opens. The Trust differs by 1,800 USD: inside the tolerance, no case.
2. **Intake (Mei).** Drop the amended Fund A statement (10,180,000 USD, final). It supersedes the 2 Oct estimate (10,000,000 USD, valued 30 Sep). Check the match "EG Growth Fund I" to Evergreen Growth I and confirm the read.
3. **Action Desk (Mei, then Raj).** The revision opens a case worth 180,000 USD against the September report. Mei takes it and submits an explanation; Raj checks it. Maker and checker are different people.
4. **CIO Brief (Daniel).** The September report as issued on 3 Oct shows 57.60m USD. As known now it shows 57.78m USD, Fund A "Revised". Ask "Why did this move?" and read the sources. Ask the agent to raise the official NAV and it refuses and opens a case.
5. **Rules (Grace, Raj).** Admin shows the signed rules: cash tolerance 5,000 USD, CIO materiality 100,000 USD or 0.5% of a fund, estimates for the investment report only, statements due in 10 business days.

## Known limits
Every analyst holds both the data engineer and the head of data seat, so Leo is not refused as an approver by role: the rule "head of data approves, data engineer proposes" holds by account only. Do not expect a refusal when Leo approves a mapping he did not propose.

The amended statement is deliberately not loaded. Nothing here uses real data.
