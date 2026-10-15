# UC8 live test plan: do our trades agree with the administrator?

Scope: liquid trades (equities and bond) and OTC FX forwards for Evergreen Family Trust (EG-TRUST), portfolio EG-LIQUID. Four monthly cycles: July, August, September and October 2026. Synthetic data only. Evergreen Office is the demo company (family office). Use no other company, person or prospect name.

Expected results come from `docs/demo/uc8/ANSWER-KEY.md`. Where the code says something different, the step says **[risk]** and the tester records what the product actually does. A prediction is never a pass.

This plan is for a real person working the way a team would: sign in as each role, drop files, press buttons, read screens. Rules:
- Do not edit product code (`sh_platform/`, `ui/src/`). Record problems, do not fix them.
- Do not touch the repo `data/` folder. Do not use ports 8400, 8504 or 8200.
- Temp files go to `D:/Temp`. Test-environment files go to `.sh-tmp/testenv/uc8/`.
- Do not write data into the warehouse by hand. Every change goes through the UI, or through the HTTP API the UI calls.
- Do not commit or push.

Repo root (used in every command below): `/d/Projects/01-Project Signal Harbor/Repo 1.0`

---

## 0. Gate and predictions (read before the first run)

### 0.1 Blocking: the seed conflict

`tools/seed_demo_boot.py` seeds the 10-use-case universe (`tools/seed_10uc.py`, `docs/test/10uc_universe.json`). That universe already holds the UC8 trades on other dates and with other ids (Northwind T-20261002-003, Harborview T-20261006-005, FXF-2026-002 T-20261005-004, dated 2, 6 and 5 October). The monthly files use September dates (T-20260917-004, T-20260930-008, T-20260929-F02). A fresh server loaded with both double-counts the same instruments.

Before the first run, Nitin chooses one option (see ANSWER-KEY "Conflicts"):
- **A (recommended):** change the UC8 rows in the seed code so they match the files (the files follow the brief). Rebuild the seed from code. Do not hand-edit warehouse data.
- **B:** move the files' story to October in `tools/make_uc8_data.py` and regenerate.
- **C:** keep the universe as it is and stop UC8 until A or B is built.

Gate check, after the server starts (step 1.5): open **Map, Data model** and look for `transactions` rows whose `external_trade_id` starts with `T-2026` and matches any UC8 id above. If the universe ids are present alongside the file ids, stop and record a **blocking** issue. Do not continue.

Record the decision and the check result in the run log (section 9).

### 0.2 Predictions from reading the code (checked in the run, not assumed)

These come from `sh_platform/v1/e3_recon.py` (`_trades`, `_run_detail`) and the screens. Each is checked in the step named.

| Id | Prediction | Code evidence | Checked at |
|---|---|---|---|
| P1 | The August timing item (same trade id, date one business day later, same amount) is raised as a **"Trade differs"** break, not a net-0 timing item. It opens a case. "Close as timing" may not be offered. | `_trades`: a pair whose `trade_date` differs goes to `found` with the label "Trade differs"; the timing button shows only when the item has `timing` set (`ui/src/v1/a5/ActionToday.tsx:184`). | 4.6 (Aug, step 5.4) |
| P2 | The 30-day window hides Harborview from the October run. As-at 30 Oct sees trades dated 1 to 30 Oct. As-at 31 Oct drops the 1 Oct trade. | `start = on - timedelta(days=29)` in `_trades`. | 7.2 |
| P3 | The October administrator file's amendment rows for September trades (Northwind, FX) are outside the 30-day window on both sides, so the October run cannot see the cure. The September cases close by a person, not by the engine. | Same window; both sides filtered by `start <= d <= on`. | 7.3 |
| P4 | Northwind quantity (same id, amount differs by 75,870.00 USD) is raised as a break with the amount. | `_trades` amount comparison, `cash_amount`. | 5.5 |
| P5 | FX forward: the engine compares the SGD amounts (4,027,500.00 vs 4,035,600.00), converted to USD at the as-at date's rate (`_convert`, as-at 30 Sep). It does not compare the quoted rates 1.3425 vs 1.3452 as rates. Expected USD figure 6,039.37 at 1.3412. | `sized()` and `_convert(plane, diff, ccy, tccy, on, cutoff)`. | 5.5 |
| P6 | Harborview (in export, not at administrator): an unmatched trade, break for the full 592,000.00 USD. | Unmatched branch of `_trades` (the `rest` list). | 5.5 |
| P7 | No signed `cash_tolerance` rule means every trade check is refused with HTTP 409 (text from `NO_RULE`). | `_run_detail`: `if not tol: raise Refused(409, ...)`. | 4.7 (before the rule is signed, as evidence) |
| P8 | Intake takes only `.xlsx`, `.xlsm`, `.csv` (`e0c_landing.py`). The OTC PDFs cannot land through intake. They go through the architecture sample route with marked fields, which is not a monthly intake. | `SPREADSHEETS` in `e0c_landing.py`; `samples/{sid}/pdf` in `b10_routes.py:74`. | 5.1, 6.1, 7.1 |
| P9 | Running the same check twice for the same as-at date may open duplicate cases. | `_run_detail` appends a run record each time; `opened` is returned per run. | 5.6 (run July again, record) |
| P10 | Builder go-live accepts `no_benchmark` (July has no prior report). | `b11_routes.py:8`: `go-live {accept_variance?, no_benchmark?}`. | 4.9 |

---

## 1. Start the tester's own server (port 8813)

1.1 Clean the environment (simple mode: `DATABASE_URL` and `REDIS_URL` both unset, `sh_platform/mode.py` refuses a half-set pair). Run in Git Bash:

```sh
unset DATABASE_URL REDIS_URL
export TMP=/d/Temp TEMP=/d/Temp TMPDIR=/d/Temp
cd "/d/Projects/01-Project Signal Harbor/Repo 1.0"
mkdir -p .sh-tmp/testenv/uc8/data
```

The data root is `.sh-tmp/testenv/uc8/data` (inside the uc8 folder). `serve_test.py` writes its log to the data root's parent, so the log lands at `.sh-tmp/testenv/uc8/server.log`.

1.2 Check port 8813 is free. PowerShell: `netstat -ano | findstr :8813` must print nothing. If it prints a line, stop and record it.

1.3 Seed the data root (idempotent, creates `_control/seed_credentials.txt`). Do not print that file.

```sh
python tools/seed_demo_boot.py --data-root "/d/Projects/01-Project Signal Harbor/Repo 1.0/.sh-tmp/testenv/uc8/data"
```

Record the `demo-ready ...` lines and the final `Demo boot: seeded.` line. Optional: `SH_DEMO_PASSWORD` (12+ characters) sets one shared password. It is read from the environment and never printed. To start again from nothing, add `--reset --data-root ...` (it wipes only that folder and refuses the repo `data/`).

1.4 Start the server with the scheduler off, as a background shell command (it is long-lived, not an agent):

```sh
python tools/serve_test.py --port 8813 --data-root "/d/Projects/01-Project Signal Harbor/Repo 1.0/.sh-tmp/testenv/uc8/data" &
```

Check the log has no error lines: `grep -i error .sh-tmp/testenv/uc8/server.log`.

1.5 Health check and mode check. Open `http://127.0.0.1:8813/login` in the browser. Sign in as Daniel Foo (section 2). The line under the agent must read **Testing models (free tier)**. The text comes from `ui/src/v1/router/ModeLine.tsx`. If it reads **Real-use models**, stop and switch back to Testing. Never use Real use in this test (the OpenRouter credit is low, and Real-use calls fail with HTTP 402, see `docs/test/AGENT-TRIAGE.md`).

1.6 Record the seed output, the server start line, the mode line text and the server PID (`netstat -ano | findstr :8813`).

1.7 Stop the server at the end: find the PID on 8813 and stop only that PID. Do not stop any other process.

---

## 2. Sign-ins and how to drive the product

### 2.1 People (from the run sheet, `docs/demo/showcase/RUN-SHEET.md`)

Emails: `<first>.<last>.evergreen@example.test`. Passwords are in `.sh-tmp/testenv/uc8/data/_control/seed_credentials.txt`, or the shared password from 1.3. Read them yourself. Never write them into the run log, a chat or a screenshot.

| Person | Product role | Used in UC8 for |
|---|---|---|
| Daniel Foo | sponsor (CIO) | Signs the intent, approves the starter dashboard, sees the Harborview item on Today |
| Mei Chen | owner (business owner) | Writes the intent with North, chases breaks, takes and dismisses cases |
| Raj Patel | approver | Approves the Northwind correction and the FX rate decision |
| Anita Rao | head of data (also analyst) | Approves the design pack, the build plan, the rule versions, the model change |
| Leo Park | data engineer and ops | Drops and loads files, runs the builder, runs the trade check, reads Operations |
| Sofia Reyes | risk owner | Reads the Harborview case and asks a question; cannot act on it |
| Grace Ong | administrator | Only checks access to Settings (roles slide), not used in the UC8 run |

Sign in once per person, in a separate browser context per person (the UC4 walkthrough did this). Record the screen each person lands on.

Route rights come from `sh_platform/route_permissions.yaml` and `sh_platform/v1/*.permissions.yaml` (for example `e3b.permissions.yaml`: the trade check is company_admin or analyst only; the recon history is readable by sponsor, approver and participant). A 403 is a finding: record the role and the route, and go on with the person who holds the right.

### 2.2 Driving the product

Preferred: the product UI through Playwright (headless Chromium), the same way the UC4 walkthrough did. Make the tester's copy of the helper:

```sh
cd "/d/Projects/01-Project Signal Harbor/Repo 1.0"
mkdir -p .sh-tmp/testenv/uc8/shots .sh-tmp/testenv/uc8/api
cp .sh-tmp/uc4w/lib.py .sh-tmp/testenv/uc8/lib.py
sed -i 's#http://localhost:8697#http://127.0.0.1:8813#; s#testenv/uc4demo/data#testenv/uc8/data#' .sh-tmp/testenv/uc8/lib.py
```

Then check the two replacements took: `grep -n "8813\|uc8/data" .sh-tmp/testenv/uc8/lib.py` must print the `BASE` line and the `CRED` line. The helper signs in at `/login` with fields `#email` and `#password`, and sends the `sh_csrf` cookie as `X-CSRF-Token` on API calls. It writes screenshots under `OUT` (set `OUT` to `.sh-tmp/testenv/uc8/shots` in the same copy if the helper still points to the UC4 folder).

API calls (no screen, or the screen does not do the action): use `W.api(method, path, body)` from the helper, which uses the same session as the UI. Keep each JSON response in `.sh-tmp/testenv/uc8/api/<step>.json` with passwords and tokens removed.

Screen paths (confirmed in `ui/src/App.tsx` where marked):
- `/centre/intent/new` (new intent, North chat). Reached from the Build centre, New.
- `/centre/intent/{IID}/charter` (the sign page, `ui/src/intents/views/CharterView.tsx`).
- `/centre/build/architecture` (architecture, Span). `/centre/build/pipelines` (Build the data, source cards). `/centre/build/prove` (builder checks). Confirmed in `App.tsx`.
- `/centre/action` (Action). Its Reconciliations group has the trade check (`ui/src/v1/a5/ReconPage.tsx`).
- Operations: Build centre, Operations (Runs with run IDs).
- Map, Data model: Map centre, Data model.
- Consume: `/consume/views`.

Where a path does not open, record it as a finding and navigate from the menu.

---

## 3. Source files

Root: `docs/demo/uc8/sources/`. Business days only (weekdays). Header-only CSVs are days with no trades.

| Cycle | Daily exports | Administrator file | Other files | As-at date for the trade check |
|---|---|---|---|---|
| July | `2026-07/trading_export_YYYYMMDD.csv` (23 files, 1 to 31 Jul) | `2026-07/administrator_trade_confirmations_2026-07.xlsx` | none | 2026-07-31 |
| August | `2026-08/` (22 files, 3 to 31 Aug) | `2026-08/administrator_trade_confirmations_2026-08.xlsx` | none | 2026-08-31 |
| September | `2026-09/` (22 files, 1 to 30 Sep) | `2026-09/administrator_trade_confirmations_2026-09.xlsx` | `2026-09/otc_confirms/FXF-2026-001_confirmation_2026-09-15.pdf`, `2026-09/otc_confirms/FXF-2026-002_confirmation_2026-09-29.pdf` | 2026-09-30 |
| October | `2026-10/` (22 files, 1 to 30 Oct) | `2026-10/administrator_trade_confirmations_2026-10.xlsx` (holds the 6 Oct amendment rows) | `2026-10/otc_confirms/FXF-2026-002_confirmation_amended_2026-10-06.pdf` | 2026-10-30 (and 2026-10-31 as a second run, see 7.2) |

List the real files before a cycle: `ls "docs/demo/uc8/sources/2026-07" | wc -l` (expect 24: 23 CSV and 1 XLSX). Do the same for each month. A count that differs from the table is a finding.

Arrival: a real person gets the files about 2 to 4 business days after month-end (run dates on the answer key: 4 Aug, 2 Sep, 2 Oct, 3 Nov). Record the arrival date in the run log. Do each month's work only after its files are in place.

Intake and upload limits (confirmed in code):
- Pipelines and intake take `.csv`, `.xlsx`, `.xlsm`. A PDF is refused there.
- A PDF goes only through the architecture sample (section 4.4). It has to be marked once; the monthly PDF must be marked again (P8).

---

## 4. Month 1: July 2026 (full build, then go live)

Expected for the July run: compared 4 trades, matched 4, breaks 0, net break 0.00 USD. Administrator footer total USD 1,408,050.00. Trades: T-20260706-001 Meridian Foods buy 15,000 at 31.20 (468,000.00); T-20260714-002 Bay Street Utilities sell 5,000 at 45.60 (228,000.00); T-20260721-003 Coastal Rail 5.1% 2031 bond buy 500,000 at 0.9915 (495,750.00); T-20260728-004 Coastal Rail Holdings buy 3,000 at 72.10 (216,300.00).

### 4.1 Intent with North (Mei Chen, by chat)

1. Sign in as Mei Chen. Go to Build, then New (`/centre/intent/new`). The North chat is the only input (no form).
2. Type this brief (in your own words if you like, keep the facts):

   > Each month I need to know whether our trades agree with the administrator, trade by trade, for the liquid book and for our OTC FX forwards. Leo and I prepare it, Daniel signs it, Anita approves the design. The trading export is one CSV per business day. The administrator sends a monthly Excel trade file. Harbour Bank sends FX forward confirmations as PDFs. The figures are: trades compared, trades matched, breaks, net break in USD, and breaks above the 5,000 USD allowance. Readers: me, Raj Patel, Sofia Reyes and Daniel Foo. Monthly, five business days after month-end. Portfolio EG-LIQUID, entity EG-TRUST.

3. Answer North's questions one at a time. Record each question and each answer.
4. Expected: four or five sources named (trading export, administrator Excel, Harbour Bank PDFs, optional market data); the figures named; the readers named; monthly cadence.
5. **[risk]** North may get a sign or unit wrong (UC4 saw a basis-point error). Read the closing summary line by line. Record any error. Do not correct it in the product.
6. Record the closing summary text and the intent id (IID, from the URL).

Screenshot M1: the closing summary.

### 4.2 Sign the intent (Daniel Foo)

1. Sign in as Daniel Foo. Open `/centre/intent/{IID}/charter`.
2. Read the sign page. Click the sign control on the page (its label is shown on screen; record it). The API equivalent is `POST /api/intents/{IID}/charter/sign`.
3. Expected: the intent is signed and read-only. A later change would be a new version.

Screenshot M2: the signed line.

### 4.3 Build-ready check (Mei Chen)

Run the build-ready check on the intent: `POST /api/intents/{IID}/build-ready/check`, or the screen that shows the check (`/centre/intent/{IID}/build-ready`). Expected: the seven lines read from records (`intents/build_ready.py`). Record each line's state.

### 4.4 Architecture with Span (Anita Rao)

1. Sign in as Anita Rao. Open `/centre/build/architecture` for the project created from the intent. Find the project id (PID): `GET /api/v1/intents/{IID}/project` (the UC4 walkthrough used this route, `.sh-tmp/uc4w/s05.py`).
2. Span lists the sources and asks what it is missing (sample files, grain, checks, freshness, access).
3. Upload the July samples:
   - the July administrator Excel: `POST /api/v1/build/p/{PID}/architecture/samples/{SID}/table` (multipart, Excel or CSV);
   - one July trading export CSV for the trading side (same route, a different `SID`).
   Get each `SID` from the architecture screen or `GET /api/v1/build/p/{PID}/architecture` (read the response for the system ids).
4. Mark each sample: `POST /api/v1/build/p/{PID}/architecture/samples/{SID}/mark` (read the body in `sh_platform/v1/b10_routes.py` lines 87 to 95 before the call).
5. Set the checks Span proposes: control totals for the administrator file (count 4, USD net 1,408,050.00 when it is the July file), key `external_trade_id`, tolerance 5,000 USD (the cash_tolerance rule is set in 4.7, not here), freshness five business days.
6. **Model extension [risk]:** the FX forwards need a place in the silver model. Record whether Span proposes a new silver table (for example for the OTC confirmations), whether it proposes a change to `transactions`, or whether the existing `transactions` table carries FX rows (`transaction_type` fx_forward). Record the proposal text. A proposed table waits for Anita: `POST /api/company/build/span/model-draft`, then `POST /api/company/build/span/model-draft/{draft_id}/file` (filed by an analyst). Anita approves it in Map, Data model.
7. Generate the pack: `POST /api/v1/build/p/{PID}/architecture/pack/generate`. Record the pack version.

Screenshot M3: the pack summary with the sources and checks.

### 4.5 Approve the design pack and the build plan (Anita Rao)

1. `POST /api/v1/build/p/{PID}/architecture/pack/submit`, then `POST .../pack/approve`. Expected: the pack is approved and locked for the builder. A later change is a new version (`pack/diff` shows what changed).
2. Propose and approve the build plan: `POST /api/v1/build/p/{PID}/plan/propose`, then `POST /api/v1/build/p/{PID}/plan/approve`.
3. **[risk]** UC4 saw the head of data approve twice (pack and plan). Record whether this happens again.

Screenshot M4: the approved pack.

### 4.6 Rules: the cash tolerance (Anita proposes, Raj approves)

The trade check needs a signed `cash_tolerance` rule in force for the as-at date (P7). Propose and approve it as two different people.

1. As Anita: `POST /api/v1/rules/cash_tolerance` with body:
   ```json
   {"definition_text": "Trades from the administrator and the trading export agree within 5,000 USD for trade checks on EG-TRUST.",
    "parameters": {"abs_amount": 5000, "currency": "USD"},
    "effective_from": "2026-07-01",
    "rule_type": "cash_tolerance"}
   ```
   Record the returned rule version id (`vid`). Use `GET /api/v1/rules` to see the current rules.
2. As Raj Patel (a different person from the proposer): `POST /api/v1/rules/versions/{vid}/approve`. Expected: approved and in force from 1 Jul 2026. Record the response.
3. Also propose `cio_materiality` if the product asks for it (`POST /api/v1/rules/cio_materiality`). Record what the product asks for, and the body it accepts (read `e3a_routes.py` and `e3_rules.py` if the body is refused).

Before this rule is signed, run the trade check once and record the 409 text (P7), as evidence.

### 4.7 Land the July files (Leo Park)

Upload path 1 (the Pipelines screen, real UI):
1. Sign in as Leo Park. Open `/centre/build/pipelines`.
2. Each source has a card. The card for the trading export has a hidden file input labelled **"Drop a file for <source name>"** (the input accepts `.csv` and `.xlsx`). Use the card's drop or choose control, pick one file, and read the note the screen shows: `<file> landed for <source>, <rows> rows. Press Run now to load it.`
3. Click **Run now** on the card. A browser confirmation appears ("Run <source> now?"): press OK. Read the note: "Run for <source> started."
4. Repeat for each file. **[risk]** 23 July trading files means 23 drops and 23 runs, which is a real cost (record minutes and clicks). Check whether a second drop replaces or adds to the first (`GET /api/company/build/pipelines` shows the plan; check the run log in Operations).
5. Drop the July administrator Excel the same way on the administrator card.
6. Source card names: the demo bronze sources are `administrator` (export) and `trading_export` (export) (`sh_platform/v1/e0a_catalogue.py:771`). Record the names the cards show.

Upload path 2 (API the UI calls): `POST /api/company/build/pipelines/{source}/upload`, multipart. The form field name is the one `ui/src/pages/PipelinesPage.tsx` line 153 appends. Check it with `grep -n "append" ui/src/pages/PipelinesPage.tsx` before the first call.

Upload path 3 (the intake, if the Pipelines card is not available): `POST /api/v1/intake/upload`, multipart, field **`data`** (not `file`; `sh_platform/v1/e0c_routes.py` line 91), optional `source_code`, then `POST /api/v1/intake/files/{file_id}/profile` and `POST /api/v1/intake/files/{file_id}/load`. Record which path was used.

Record for each file: name, rows, status, the run id.

Screenshot M5: the Pipelines screen with the July cards.

### 4.8 Builder runs on a copy (Leo Park)

1. Open `/centre/build/prove` (builder checks) or the Pipelines build for the project. Start the builder: `POST /api/v1/build/p/{PID}/builder/start`. Settle any open items: `POST .../builder/settle`. Recheck: `POST .../builder/recheck`.
2. Read the builder state: `GET /api/v1/build/p/{PID}/builder`.
3. Record the TEST run id from `GET /api/v1/ops/runs?mode=test` (Operations, Runs, TEST badge).
4. Expected: the copy is built from July's files only. Check the figures against the answer key:
   - July totals: 4 trades; 468,000.00, 228,000.00, 495,750.00, 216,300.00 USD.
   - Net break 0.00 USD.

Screenshot M6: the builder checks.

### 4.9 Benchmark (no prior report in July) and go-live (Leo Park)

1. There is no prior report for July. Record what the builder does with no benchmark (R10 / P10). If it asks for one, use the answer-key July summary as a file: `POST /api/v1/build/p/{PID}/builder/benchmark` with body `{"name": "UC8 answer key July 2026", "text": "<the July rows as text>"}` (the body shape is in `sh_platform/v1/b11_routes.py` line 7, either `{name, text|b64}` or `{report_version_id}`). Record the response.
2. Go live: `POST /api/v1/build/p/{PID}/builder/go-live`. If the builder refuses without a benchmark, send `{"no_benchmark": true}` and record that this was needed.
3. Expected: the project is live. The production run appears in Operations as a PRODUCTION row with a run id (run id format `run-YYYYMMDD-HHMMSS-xxxx`). Record it.

Screenshot M7: Operations, Runs, with the PRODUCTION row.

### 4.10 Run the trade check on July (Leo Park or Anita Rao)

1. Sign in as Leo Park. Open Action (`/centre/action`), then the **Reconciliations** group.
2. In the screen, set **Check as at** (a date field) to **2026-07-31**. Press **Run now** on the trade check (its code is `trade_vs_admin`).
3. Or by API: `POST /api/v1/recon/trade_vs_admin/run` body `{"as_of_date": "2026-07-31"}`.
4. Expected: `checked` 4, `breaks` 0, `opened` empty, `skipped` empty. Each trade id is matched.
5. Record the response and the entry from `GET /api/v1/recon/runs`. Record the run id if one shows.

Screenshot M8: the Reconciliations screen after the July run.

### 4.11 Starter dashboard and approval (Mei submits, Daniel approves)

1. Lumen proposes the starter: `POST /api/v1/build/p/{PID}/studio/starter`. Record the tiles and their values. Expected tiles: trades compared, matched, breaks, net break USD, breaks above allowance. **[risk]** Check each tile's unit and whether a figure is missing (the allowance).
2. Mei submits: `POST /api/v1/build/p/{PID}/studio/{DID}/submit`.
3. Daniel approves: `POST /api/v1/build/p/{PID}/studio/{DID}/approve`. Read the panel "What Lumen checked": it must name the run it checked and the signed version, not "No reviewed run is on record".
4. Expected: the dashboard is approved; Daniel sees it under "Waiting for my approval" on Action before he approves.

Screenshot M9: the approved starter dashboard.

### 4.12 Month 1 end state

- July production run in Operations with a run id.
- July trade check: 4 compared, 0 breaks.
- Rule version signed and in force from 1 July.
- Starter dashboard approved.
- Record every issue in the issues log (section 9).

---

## 5. Month 2: August 2026 (timing item, expected to clear)

Expected: compared 4, matched 3, breaks 1 (timing, Bay Street Utilities sell T-20260827-004, export 27 Aug, administrator 28 Aug), net 0.00 USD. Administrator footer USD 925,040.00. Other August trades: T-20260804-001 Meridian buy 8,000 at 31.00 (248,000.00); T-20260811-002 Northwind buy 4,000 at 38.90 (155,600.00); T-20260818-003 Coastal Rail Holdings buy 2,000 at 73.40 (146,800.00).

### 5.1 Land the August files (Leo Park)

Repeat the July method (4.7): 22 trading CSVs (one drop and run each, or the path the product allows), then the August administrator Excel. Expected: each file loaded. If a file is already loaded from an earlier try, record `already_loaded`. Record minutes and clicks.

Screenshot M10: the Pipelines screen after the August drops.

### 5.2 Production load (Leo Park)

Run the production load: `POST /api/v1/build/p/{PID}/run`, or the Run now control on the card. Record the production run id. Check it in Operations (`GET /api/v1/ops/runs?mode=production`, and the UI's Runs list). Cross-check the two.

### 5.3 Benchmark check against July (Leo Park)

Upload the July report as last month's benchmark: `POST /api/v1/build/p/{PID}/builder/benchmark` with `{"report_version_id": "<the July report version id>"}` if the July production report exists, otherwise the text body from 4.9. Expected: the builder compares August with July line by line (Matches, Explained, Unexplained). Record each line.

### 5.4 Run the trade check as at 31 Aug (Leo Park)

Action, Reconciliations, Check as at **2026-08-31**, Run now. Or `POST /api/v1/recon/trade_vs_admin/run` `{"as_of_date": "2026-08-31"}`.

Expected per answer key: 1 timing item, net 0.00 USD, and it is cleared without a case.

**[risk P1]** Predicted by code: the item is a "Trade differs" break (same id, one business day later date), opened as a case with net 0.00. Record:
- `checked`, `breaks`, `opened` (the case ids) and the case wording;
- whether the Action line shows **Close as timing**;
- the case text on the timing item.

Screenshot M11: Action, Reconciliations, the August item.

### 5.5 Close the timing item (Mei Chen)

1. Sign in as Mei Chen. Action, Reconciliations, the Bay Street line.
2. If **Close as timing** is shown, press it (it dismisses the case with the reason "A timing difference that clears by itself."). Record the reason shown.
3. If the button is not shown, open the case (**Take the case**), then **Dismiss with reason** with the reason text: `Administrator booked 28 Aug, one business day after our 27 Aug trade.` Record that the timing button was not offered (P1).
4. API equivalent: `POST /api/v1/cases/{cid}/dismiss` body `{"reason": "Administrator booked 28 Aug, one business day after our 27 Aug trade."}`.
5. Expected: the item is closed and nothing else needs doing; net break 0.00 USD.

Screenshot M12: the closed item.

### 5.6 Repeat check (P9)

Run the August check a second time with the same as-at date. Record `opened` and whether a second case appears for the same trade. Record the result as P9 pass or fail.

### 5.7 Read Operations and Action (Leo Park, Mei Chen)

Operations shows the August runs with their ids. Action no longer lists the closed item. Record any remaining August item.

### 5.8 August end state

- August production run in Operations with a run id.
- One timing item closed by Mei with a reason.
- Net break 0.00 USD.

---

## 6. Month 3: September 2026 (three real breaks, OTC PDFs)

Expected: compared 8, matched 5, breaks 3, net break total 673,909.37 USD, excess over the 5,000 allowance 658,909.37 USD. Administrator footer USD 1,832,780.00 and SGD 6,715,600.00 (7 rows; Harborview not booked).

| Break | Trade | Expected | Over allowance by |
|---|---|---|---|
| U2 | T-20260917-004 Northwind Logistics buy: export 12,000 at 42.15 (505,800.00), administrator 10,200 (429,930.00) | quantity, net 75,870.00 USD | 70,870.00 |
| U3 | T-20260929-F02 FXF-2026-002 sell USD 3,000,000, buy SGD: export rate 1.3425 (SGD 4,027,500.00), confirmation 1.3452 (SGD 4,035,600.00); SGD 8,100 at 1.3412 | price (rate), net 6,039.37 USD | 1,039.37 |
| U4 | T-20260930-008 Harborview Semiconductor sell 5,000 at 118.40 (592,000.00) | missing at the administrator, net 592,000.00 USD | 587,000.00 |

Matched: T-20260903-001 Meridian (10,000 at 32.10); T-20260910-002 Bay Street sell (6,000 at 47.30); T-20260915-F01 FXF-2026-001 at 1.3400 (SGD 2,680,000.00); T-20260922-005 Coastal Rail Holdings (4,000 at 75.60); T-20260929-007 Coastal Rail bond (500,000 at 0.9913).

### 6.1 Land the September files (Leo Park)

1. Drop the 22 September trading CSVs and run each (method 4.7). Drop the September administrator Excel.
2. The two OTC PDFs (`FXF-2026-001_confirmation_2026-09-15.pdf`, `FXF-2026-002_confirmation_2026-09-29.pdf`) do not go through Pipelines or intake (P8). Use the architecture sample for the OTC source:
   - `POST /api/v1/build/p/{PID}/architecture/samples/{SID_OTC}/pdf` (multipart, the PDF file).
   - Mark the fields once: trade id, trade date, currency pair, rate, SGD amount, USD amount, counterparty. The mark call is `POST /api/v1/build/p/{PID}/architecture/samples/{SID_OTC}/mark` (body in `b10_routes.py` lines 87 to 95). Use the line-by-line view (`GET .../samples/{SID_OTC}/lines`) to pick each field.
   - Record the values read for FXF-2026-002: rate 1.3452, SGD 4,035,600.00.
3. **[risk R8]** The PDF may not read cleanly (the UC4 walkthrough found table cells on separate lines). If the marked values are wrong, record it and do not fix the PDF.
4. Confirm the read values in the evidence queue (`/centre/extract/review`). Record what was confirmed and any value corrected.

Screenshot M13: the PDF sample with the marked fields.

### 6.2 Production load and the trade check as at 30 Sep (Leo Park)

1. Run the production load (5.2). Record the run id.
2. Action, Reconciliations, Check as at **2026-09-30**, Run now. Or `POST /api/v1/recon/trade_vs_admin/run` `{"as_of_date": "2026-09-30"}`.
3. Expected: `checked` 8, `breaks` 3, `opened` 3 cases, net break total 673,909.37 USD.
4. Check each break against the table above:
   - **U2 quantity:** the case text names the amounts. **[risk R3]** The engine may say "Trade differs" or "mismatch" without naming "quantity". Record the wording. P4 predicts the net 75,870.00 USD and the 70,870.00 excess.
   - **U3 price:** P5 predicts the engine compares SGD 8,100 converted to USD at the 30 Sep rate. Record the USD figure. Expected 6,039.37 USD; if the rate is different, record the figure and the rate used. Record whether the quoted rates 1.3425 and 1.3452 appear anywhere (they should not, per P5).
   - **U4 missing:** P6 predicts 592,000.00 USD, the full amount, as an unmatched trade.
5. Record `checked`, `breaks`, `opened` (case ids) and the net total.

Screenshot M14: the Reconciliations screen with the three September items.

### 6.3 Northwind quantity (U2): Mei Chen and Raj Patel

1. Mei Chen: open the U2 case. **Take the case** (`POST /api/v1/cases/{cid}/take`).
2. Mei writes a note: `POST /api/v1/cases/{cid}/note` body `{"text": "Export 12,000, administrator 10,200. Asked the administrator and the trading desk which quantity is right."}`. She contacts the administrator and the trading desk outside the product; nothing is sent from the product.
3. Mei asks Tally the question if she wants: `POST /api/v1/cases/{cid}/ask` body `{"question": "What is the difference on this item?"}`. Record the answer.
4. Mei sends the case for approval: `POST /api/v1/cases/{cid}/submit` body `{"explanation": "Waiting for the administrator to confirm the quantity.", "checker": "<Raj Patel's user id, if the product asks for it>"}`.
5. Raj Patel (approver): approve the decision to ask for a correction: `POST /api/v1/cases/{cid}/approve`. Record the note. Raj approves the request, not the closure (the closure is in October).
6. Record every action, its time, and who saw it.

### 6.4 FX rate (U3): Raj Patel decides, Mei Chen tracks

1. Raj decides the agreed rate (1.3425 or 1.3452): a note on the case, `POST /api/v1/cases/{cid}/note` `{"text": "Rate to use: <rate>. Ask Harbour Bank for a corrected confirmation."}`. Nothing is sent to Harbour Bank from the product.
2. Mei tracks it: note `Waiting for the amended confirmation from Harbour Bank.`
3. Expected: one case open at 6,039.37 USD (1,039.37 over the allowance), waiting for the amended confirmation (it arrives on 6 Oct, section 7).

### 6.5 Harborview missing (U4): Mei Chen chases, Sofia Reyes informed, Daniel Foo sees it

1. Mei: take the U4 case, add the chase note: `Asked the administrator why this sell is not booked.`
2. Sofia Reyes (participant): sign in and open Action and the case. Expected: she can read the case and ask a question (`POST /api/v1/cases/{cid}/ask`), but cannot take, submit, approve or dismiss (the route rights say so). Record exactly what she sees and what the buttons do. Nothing is emailed; the run sheet says email is a preview only.
3. Daniel Foo: open Today (or Action). Expected: the 592,000.00 USD item is on his list because it is the largest. Record where it appears.

Screenshot M15: the Harborview case as Sofia sees it.

### 6.6 Action check (Anita Rao)

Action, Reconciliations: the three September items with their amounts. Expected: none of the three offers **Close as timing** (they are real breaks). Record any that does.

### 6.7 September end state

- Three open cases (U2, U3, U4); net break total 673,909.37 USD.
- U2 and U3 have approval or ask notes; U4 has the chase note.

---

## 7. Month 4: October 2026 (two cleared, one carried forward)

Expected for October's new trades: compared 3, matched 3, new breaks 0. Trades: T-20261001-009 Meridian buy 20,000 at 33.10 (662,000.00); T-20261002-010 Bay Street sell 10,000 at 48.20 (482,000.00); T-20261007-011 Coastal Rail bond buy 1,000,000 at 0.9910 (991,000.00). Open at 31 Oct: Harborview T-20260930-008, 592,000.00 USD, 587,000.00 over the allowance. Administrator footer USD 2,135,000.00 (3 trades; amendments not in the footer). SGD 0.00.

Amendments (booked 6 Oct): Northwind T-20260917-004 quantity corrected to 12,000 = 505,800.00. FX FXF-2026-002 rate corrected to 1.3425 = SGD 4,027,500.00 (the amended confirmation PDF).

### 7.1 Land the October files (Leo Park)

1. Drop the 22 October trading CSVs and run each (method 4.7).
2. Drop the October administrator Excel. Check the amendment rows: Northwind and FX appear once each, with the corrected figures. **[risk R9]** Record whether the amendment rows create a second trade or a duplicate break.
3. Add the amended FX confirmation PDF through the architecture sample route (as 6.1), marking the fields again. Record the values read: rate 1.3425, SGD 4,027,500.00.

Screenshot M16: October intake with the amendment rows.

### 7.2 Trade check as at 30 Oct (and 31 Oct as a second run)

1. Run the production load. Record the run id.
2. Action, Reconciliations, Check as at **2026-10-30**, Run now. Or `POST /api/v1/recon/trade_vs_admin/run` `{"as_of_date": "2026-10-30"}`.
3. Expected from the answer key: 3 new trades matched; no new breaks. **[risk P2]** Predicted by code: the window is 1 to 30 Oct, so Harborview (30 Sep) is outside and does not appear in this run. Record `checked`, `breaks` and any open item listed.
4. Run again with **2026-10-31**. **[risk P2]** Predicted: the window becomes 2 to 31 Oct, so the 1 Oct trade (T-20261001-009) drops out of the check. Record `checked` (expected 2 instead of 3) and whether the difference is explained.
5. The answer key is the 30 Oct run. Record both runs side by side.

### 7.3 Amendments and the window (P3)

The September cases (U2, U3) are not in the October run's window. The engine does not see the administrator's amendment rows for them (P3). So the cure must be recorded by a person.

Record: whether the October run lists U2 or U3 at all. Expected by the code: no.

### 7.4 Close the Northwind break (Mei Chen, with Raj Patel's sign-off)

1. Mei: open the U2 case. Note: `Administrator amendment 6 Oct: quantity corrected to 12,000 = 505,800.00.` Submit: `POST /api/v1/cases/{cid}/submit` `{"explanation": "Administrator amendment 6 Oct clears the quantity break.", "checker": "<Raj Patel>"}`.
2. Raj: approve the closure: `POST /api/v1/cases/{cid}/approve`. Record the note.
3. Expected: the case is closed (state in the response) with the amendment reference. Record the state text.

### 7.5 Close the FX break (Mei tracks, Raj signs off the rate)

1. Mei: note `Amended confirmation 6 Oct: rate 1.3425, SGD 4,027,500.00.`
2. Raj: sign off the FX rate: `POST /api/v1/cases/{cid}/approve` with his note `Rate agreed: 1.3425.`
3. Expected: closed with the amendment reference.

Screenshot M17: both September cases closed.

### 7.6 Harborview carried forward (Mei keeps chasing, Sofia reviews)

1. Mei: note `Still not booked at the administrator in October. Chased on <date>.`
2. Sofia: reads the case and asks a question if she wants (`ask`). Record what she sees.
3. Expected: the U4 case stays open at 592,000.00 USD. Action shows it under Reconciliations or Cases. The October run does not show it (P2); the case survives in Cases. Record where it shows.

### 7.7 Read the month (Daniel Foo, Anita Rao)

1. Consume (`/consume/views`) and the starter dashboard. Expected: the October figures and the open item. Record what the dashboard shows for the open 592,000.00 USD and whether it is in the net break figure.
2. Use **Where is this from?** on one figure. Record the source.

Screenshot M18: Consume with the open item.

### 7.8 October end state

- Northwind and FX closed with the amendment reference.
- Harborview open at 592,000.00 USD.
- October trades matched; no new breaks.

---

## 8. Milestone screenshots

Save each to `.sh-tmp/testenv/uc8/shots/<name>.png` (the helper's `shot()` writes to its `OUT`). Do not save passwords, tokens or the credentials file in a screenshot. Blur nothing; the data is synthetic.

| Id | Screen | Who | When |
|---|---|---|---|
| M1 | North closing summary | Mei | 4.1 |
| M2 | Signed intent line | Daniel | 4.2 |
| M3 | Architecture pack summary | Anita | 4.4 |
| M4 | Approved design pack | Anita | 4.5 |
| M5 | Pipelines, July cards | Leo | 4.7 |
| M6 | Builder checks | Leo | 4.8 |
| M7 | Operations, PRODUCTION run | Leo | 4.9 |
| M8 | Reconciliations, July run | Leo | 4.10 |
| M9 | Starter dashboard approved | Daniel | 4.11 |
| M10 | Pipelines, August drops | Leo | 5.1 |
| M11 | Reconciliations, August item | Leo | 5.4 |
| M12 | Timing item closed | Mei | 5.5 |
| M13 | PDF sample with marked fields | Leo | 6.1 |
| M14 | Reconciliations, three September items | Leo | 6.2 |
| M15 | Harborview case as Sofia sees it | Sofia | 6.5 |
| M16 | October intake with amendments | Leo | 7.1 |
| M17 | September cases closed | Mei | 7.5 |
| M18 | Consume, open item | Daniel | 7.7 |

---

## 9. What to record

### 9.1 Run log

`.sh-tmp/testenv/uc8/run-log.jsonl`, one line per step:

```json
{"step": "5.4", "month": "2026-08", "who": "Leo Park", "action": "Run trade check as at 2026-08-31", "via": "UI Check as at + Run now | API POST /api/v1/recon/trade_vs_admin/run", "expected": "1 timing item, net 0.00 USD, no case", "observed": "checked 4, breaks 1, opened [case id]", "run_id": "", "screen_or_response": "shots/M11.png", "result": "pass | fail | prediction-confirmed | prediction-not-seen", "issue_id": "I-003 or none", "minutes": 0, "clicks": 0}
```

Record for every step: the expected value and source (ANSWER-KEY or a P-id), the observed figure with its currency and unit, the ids (run, batch, file, case, rule version), and the verdict.

### 9.2 Issues log

`.sh-tmp/testenv/uc8/issues.md`, one entry per problem:
- id (`I-001` onward), step, month, role;
- severity: 1 blocking the month, 2 wrong figure, 3 friction (extra clicks or minutes), 4 cosmetic;
- what happened, what was expected, evidence (screen file, response excerpt, id);
- answer-key id if any (U1 to U6), or P-id;
- whether it blocks the next step, and who should look at it (product, data, or the tester).

### 9.3 Effort per cycle

For each month record: minutes and clicks for the file drops, the checks, the case actions, and the approvals, per person. This is the honest effort measure the review needs.

---

## 10. Done means

- Every step in sections 4 to 7 has a run-log line.
- Each month's expected figures are checked against the answer key; each difference is an issue.
- Every P1 to P10 prediction is marked confirmed or not seen.
- Every failure has an issue entry with its severity and what it blocks.
- The server on 8813 is stopped (step 1.7). Nothing was written to the repo `data/` folder, to ports 8400, 8504 or 8200, or to product code.

---

## 11. Decisions for Nitin before the run

1. The seed conflict (section 0.1). Blocking. Recommended: option A.
2. The October as-at date: 30 Oct (answer key) or 31 Oct (P2). Both are run in 7.2.
3. Whether the 30-day window is a product rule or a bug (P2). It decides whether a carried-forward break stays visible in a run.
4. Whether the trade check should compare FX forwards by rate, not only by SGD amount (P5).
5. Whether a September item amended in October should be seen by the October run at all (P3).
6. Whether month 1 may go live without a benchmark (P10).
7. Whether a timing item should open a case (P1), or be closed by the engine when the amount agrees and only the date differs.
