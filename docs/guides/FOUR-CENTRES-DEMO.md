# Four centres, one project: the ten-minute walk (Evergreen Office)

Synthetic data only. Evergreen Office is fictional. Seed it once (safe to repeat, changes nothing the second time):

    python tools/seed_v3_demo.py

Sign-in details are in `data/_control/seed_credentials.txt` (never printed). The project is "Monthly investment report in USD and SGD".

| Person | Sign in as | Sees |
|---|---|---|
| Daniel Foo, CIO | sponsor | Intent, Action, Consume |
| Mei Chen, Operations | analyst | Intent, Action, Build |
| Raj Patel, Finance | approver | Action, Consume |
| Anita Rao, Head of data | analyst | all four |

## 1. Intent (2 minutes), as Daniel Foo
1. Open **Intent**. The project is in the header with its id (prj-...).
2. Read the intent of work: goal, the three KPIs (net worth by entity, cash by entity, holdings by status), and its signature (Daniel Foo, version 1).
3. Open the **Process map** tab: six steps in three lanes (Operations, Finance, Investment office). The spreadsheet steps are flagged Manual.
4. Open **Sources**: the administrator export and trading export (structured, daily), manager statements (unstructured, monthly), each with its owner.

## 2. Build (3 minutes), as Anita Rao
1. Open **Build**, pick the project in the picker.
2. **Sources**: three sources, structured and unstructured shown apart.
3. **Model changes**: none. Silver is unchanged.
4. **Tables and SQL**: bronze (administrator and trading positions), silver (core tables), gold (`gold_investment_report_holdings_monthly`, `gold_investment_report_cash_daily`). Open one to read its SQL.
5. **Diagram**: sources, bronze, silver, gold, consumers.
6. **Approval**: proposed by Leo Park, approved by Anita Rao, state live.
7. **Pipeline**: a sandbox run and a live run, rows per table, schedule daily at 06:00. "Download Airflow DAG" gives the client deployment file.

## 3. Consume (3 minutes), as Daniel Foo
1. Open **Consume**, pick the project: dashboard "Monthly investment report in USD and SGD".
2. Three accepted tiles (latest month, September; August is also in the data). Net worth: Evergreen Holdings 16.40m, Evergreen Family Trust 41.20m (57.60m in all). Holdings by status: official and estimated (Fund A, 10.00m, is an estimate). Cash by entity: administrator next to trading view; Entity B differs by 12,400.
3. "Data used" on a tile names the gold table. The dashboard is shared with Daniel Foo and Raj Patel.
4. Ask Lumen: "show net worth by entity per month as a line chart" (two report months, August and September). Accept it, then "Why did this move" reads the change from the rows. "Not this" drops a tile.
5. **Share**: tick Raj Patel (the picker lists people with access to the data) and press Share. He gets a "shared with you" card in Action. Open `/centre/consume/d/dash-0ad2b1c7` as Raj for the read-only view.

## 4. Action (2 minutes), as Raj Patel
1. Open **Action**. **Today** holds the Pulse cards; a "shared with you" card appears for each person a dashboard is shared with.
2. **Cases**: the Entity B cash gap (12,400 over the 5,000 tolerance) is a case with its evidence.
3. **Reconciliations**: the cash check, last run, breaks open. On any figure, "Where is this from?" opens the trail.

## Reset
Delete `data/evergreen/build/<project id>`, `data/evergreen/consume/<project id>` and run the seed again. The intent and project are kept.
