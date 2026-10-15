# UC8 runbook: do our trades agree with the administrator? (run 2)

This runbook repeats run 2 on a clean checkout, up to where it stopped. Run 2 stopped in Month 1, after go-live was refused and before July was loaded. No product path writes uploaded trade files into silver `transactions`, and the trade check reads only that table (see UC8-REPORT.md, issue B1). Steps 1 to 12 below work. Step 13 is the blocker. Steps 14 to 16 show what would come next once B1 is fixed.

Helper scripts are in `docs/test/uc-live/uc8-scripts/`. Screenshots are in `docs/test/uc-live/uc8-run2-shots/`. API responses are kept in `.sh-tmp/testenv/uc8-run2/api/<step>.json`.

## 0. Prerequisites

- Windows, Git Bash. The repo is at `D:\Projects\01-Project Signal Harbor\Repo 1.0`.
- Python is the repo venv: `C:/Users/Nitin/Python Projects/Investment Doc Extraction/files/venv/Scripts/python.exe`, with Playwright Chromium installed.
- The UI is built (`ui/dist` exists).
- `DATABASE_URL` and `REDIS_URL` are unset (simple mode). Temp files go to D:/Temp.
- Agents run in Testing mode only (free-tier models). The mode line must read "Testing models (free tier)".
- Do not use ports 8811, 8812, 8400, 8504 or 8200, or the repo's `data/`.

## 1. Build the source files

```sh
cd "/d/Projects/01-Project Signal Harbor/Repo 1.0"
"$PY" tools/make_uc8_data.py      # PY = the venv python above
ls docs/demo/uc8/sources/2026-07 | wc -l   # 24 (23 CSV + 1 XLSX + otc_confirms dir)
```

## 2. Create the clean environment (Option A, clean company)

```sh
unset DATABASE_URL REDIS_URL; export TMP=/d/Temp TEMP=/d/Temp
"$PY" docs/test/uc-live/uc8-scripts/make_env.py "/d/Projects/01-Project Signal Harbor/Repo 1.0/.sh-tmp/testenv/uc8-run2/data"
```

This runs `tools/seed_evergreen.seed` (the company, 7 accounts, entities, portfolios, source systems, fund instruments, signed base rules) and `tools/seed_10uc._static` (the UC8 securities, the FX forward instruments, identifiers and extra signed rules). It skips the 10-use-case history, live data, trades, checks, library, `seed_v3_demo` and `seed_demo_ready`. It writes no transactions. The script refuses to run on a root that already has a company.

The signed `cash_tolerance` rule (5,000 USD, owner Raj Patel, v1) already comes with the master data, so plan step 4.6 is not needed.

## 3. Start the server (port 8813, scheduler off)

Git Bash, run in the background:

```sh
"$PY" tools/serve_test.py --port 8813 --data-root ".sh-tmp/testenv/uc8-run2/data"
```

PowerShell:

```powershell
& $PY tools/serve_test.py --port 8813 --data-root ".sh-tmp/testenv/uc8-run2/data"
```

The log goes to `.sh-tmp/testenv/uc8-run2/server.log`. To find the PID: `netstat -ano | findstr :8813`. At the end, stop that PID only: `Stop-Process -Id <pid>`.

## 4. Sign-ins

- Email: `<first>.<last>.evergreen@example.test` (mei.chen, daniel.foo, anita.rao, leo.park, sofia.reyes, raj.patel, grace.ong).
- Password: from `.sh-tmp/testenv/uc8-run2/data/_control/seed_credentials.txt`, or from `SH_DEMO_PASSWORD`. `lib.py` reads it at run time and never prints or saves it.
- Sign-in page: `http://127.0.0.1:8813/login`, fields `#email` and `#password`, then Enter.
- Run every script with `sh docs/test/uc-live/uc8-scripts/py.sh <script> [args]`. `lib.W(who)` opens headless Chromium as that person, signs in through `/login`, and makes API calls in the same session with the `sh_csrf` cookie sent as `X-CSRF-Token`.

## 5. Month 1, step 1: Mei Chen writes the intent with North (about 2 minutes per turn)

- Screen: Build > New (`/centre/build/new`). Type the text into the chat box and press **Start**. Each later turn: press **Accept** on North's drafted changes, then type and press **Send**.
- Script for the first turn: `north.py start "<text>"`.
- Script for later turns: `north.py say "<text>" <shot-name>`.

Text typed, in order:

1. (start) "Each month I need to know whether our trades agree with the administrator, trade by trade, for the liquid book and for our OTC FX forwards. Leo and I prepare it, Daniel signs it, Anita approves the design. The trading export is one CSV per business day. The administrator sends a monthly Excel trade file. Harbour Bank sends FX forward confirmations as PDFs. The figures are: trades compared, trades matched, breaks, net break in USD, and breaks above the 5,000 USD allowance. Readers: me, Raj Patel, Sofia Reyes and Daniel Foo. Monthly, five business days after month-end. Portfolio EG-LIQUID, entity EG-TRUST."
2. to 4. Answers to North's questions on visibility, the process steps, the net break definition and the July figures. The full log is in `.sh-tmp/testenv/uc8-run2/north_log.txt`.
5. "Yes, accept. Breaks above allowance is the count of breaks whose USD difference is above 5,000 USD, and we also show the excess over 5,000 in USD. Why: ... Only the people I named can see it. Team: Anita Rao is the architect, Leo Park builds it, I test it. Source owners: ..."
6. "Yes, accept all of that, and the process steps are right. Last month (July 2026): trades compared 4, trades matched 4, breaks 0, net break 0.00 USD, breaks above the 5,000 USD allowance 0. Why it matters now: ..."
7. "Yes, the extraction specs are right. Breaks above allowance and Breaks above 5,000 USD allowance are the same figure, please keep only one. Its July figure was 0. That is everything; please get it ready for Daniel to sign."
8. "The Breaks above 5,000 USD allowance figure for July 2026 was 0 and it should read 0 after the load. What the result looks like: ... How we will know it worked: ..."

Then run `accept.py`. It presses Accept on every pending change (`GET /api/v1/intents/{iid}/proposals`, then `POST .../proposals/{pid}/accept`).

Expected: the intent of work can be signed. Actual: it stayed "cannot be signed yet: What the result looks like; How you will know it worked; For each figure, what you reported last period...". North says it noted these items but never writes them (issue M1). North also asks for the same figures again in every turn (issue M2).

Screenshots: `jul-01-mei-intent-turn5/6/8.png` and `jul-01-mei-intent-drafted.png`. The earlier turns are in `m1-01-mei-north-*.png`.

## 6. Workaround W1: fill the three sections

1. `m1_fill.py` (Mei). She uses the document's **edit** controls: `PUT /api/v1/intents/{iid}/sow` with body `{"section":"template_fields","field":"result","value":"..."}`, the same for `"success"`, and `{"section":"goal","field":"why","value":"..."}`.
2. Mei is refused the benchmark sheet (403, issue M3), so Daniel fills it. `m1_bench.py` (Daniel) sends `POST /api/v1/build/{iid}/benchmarks/sheet/rows/br_8a9c09c3` with `{"reported":0,"expected":0}`.

Expected: `GET /api/v1/intents/{iid}/sow` returns `may.sign = true`.

## 7. Month 1, step 2: Daniel Foo signs

`m1_sign.py` follows the screen path `/centre/intent/{iid}/sign`: tick **I have read all N sections**, then press **Sign intent**.

Expected: SIGNED, version 1, signature Daniel Foo (sponsor).

Screenshots: `jul-02-daniel-intent-before-sign.png` and `jul-02-daniel-intent-signed.png`.

Note: `/centre/intent/{iid}/charter` returns "We could not find that" for Daniel. That is the old charter route (issue m1).

## 8. Month 1, step 3: Mei presses Send to Build

`m1_send.py` uses the North page button **Send to Build**, which calls `POST /api/v1/intents/{iid}/send-to-build`. The project is `prj-44447baa`.

Screenshot: `jul-03-mei-sent-to-build.png`.

## 9. Month 1, step 4: Leo works with Span the architect

1. `m1_arch0.py leo` opens `/centre/build/p/{pid}/architecture`. Span lists 6 sources; North created 3 duplicates (issue M4). Screenshot: `jul-04-leo-architecture-open.png`.
2. `m1_arch1.py`:
   - `POST .../architecture/systems/confirm {"ids":[trading CSV, admin monthly Excel, FX confirmations]}`.
   - Answers `POST .../questions/{grain|history|checks|definitions|freshness|access} {"value":...}`.
   - Uploads samples with `POST .../samples/{sid}/table {"name","data":base64}`, using `2026-07/trading_export_20260706.csv` and `2026-07/administrator_trade_confirmations_2026-07.xlsx`.
3. `m1_arch2.py` uploads the Sep `FXF-2026-001` confirmation PDF as the bank's layout sample (July has no PDF): `POST .../samples/{sid}/pdf`.
4. `m1_arch3.py` marks 8 lines (`POST .../samples/{sid}/mark {"line","name","format"}`) and runs `POST .../pack/generate` (Span model call, about 37 s).

Result: design pack v1 with 6 sources, **0 gold and 0 silver tables**, 20 mapping rows (12 open), 3 checks (issue B2). Screenshot: `jul-05-leo-design-pack-drafted.png`.

## 10. Workaround W2: settle the pack rows and approve

`m1_pack.py`:

1. Leo settles each open mapping row with a note: `PUT .../pack/edit {"section":"mapping","key":id,"changes":{"resolve":true},"note":...}`.
2. Leo submits: `POST .../pack/submit`.
3. Anita approves: `POST .../pack/approve`.
4. Anita draws the plan: `POST .../pack/plan`.

Screenshots: `jul-05-anita-pack-to-approve.png` and `jul-06-anita-pack-approved.png`.

## 11. Workaround W3: the build plan needs its own approval

The builder said "design pack is not approved yet" even though the pack was approved. The builder reads the newest approved **plan** (`b11_builder.pack_of`).

`m1_plan.py`:

1. Leo: `POST /api/v1/build/p/{pid}/plan/propose`.
2. Anita: `POST .../plan/approve`.
3. Leo: `POST .../builder/start`.

Result: round blocked. 2 sources are connected; 4 need a sample (the 3 North duplicates and the FX PDF). Screenshots: `jul-08-leo-pipelines-room.png` (before) and `jul-09-leo-builder-on-copy.png`.

## 12. Trade check rights

- Mei, Raj and Daniel get 403: "Anita Rao or Leo Park or Grace Ong can".
- Anita and Leo get 403: "Your access to the company's data is read-only" (issue M5).
- Only Grace (company admin) can run the check.

API call: `POST /api/v1/recon/trade_vs_admin/run {"as_of_date":"2026-07-31"}`.

## 13. Blocker B1: July trades cannot reach silver `transactions`

`m1_evidence.py` (Grace) shows:

- Map > Data model: `silver.transactions rows: 0, loaded: false`.
- Trade check as at 31 Jul: `checked 0, records {trading export 0, administrator 0}`, skipped "Nothing was reported on either side".
- Operations: two `recon` runs, PRODUCTION, by "system". There is no TEST run.

Screenshots: `jul-10-grace-trade-check-empty.png`, `jul-11-grace-map.png`, `jul-12-grace-operations-runs.png` and `jul-13-leo-action-items.png`.

Why: the intake (`/api/v1/intake/upload`, `e0c_load._TABLES`) loads positions, valuations, cash, NAV and market data, not `transactions`. The pipelines upload (`/api/company/build/pipelines/{source}/upload`) lists no pipelines in a clean company, and it names each file with today's date. The builder lands bronze only (the pack has 0 silver and 0 gold tables). The only writers of `transactions` are the seed tools. **The run stops here.**

## 14 to 16. After B1 is fixed (not run)

For each month M = 07, 08, 09, 10:

1. Land `docs/demo/uc8/sources/2026-M/*`.
2. Run the trade check as Grace with `as_of_date` = month-end (31 Jul, 31 Aug, 30 Sep, 30 Oct).
3. Compare with ANSWER-KEY:
   - Jul: 4/4/0, net 0.
   - Aug: 4 compared, 3 matched, 1 timing break (T-20260827-004), net 0.
   - Sep: 8/5/3, net 673,909.37 USD, excess 658,909.37.
   - Oct: 3/3/0 new; Harborview T-20260930-008 carried at 592,000.00.

Then take the actions on Action > Cases and read Consume. Predictions P1 to P3 in UC8-PLAN.md say the 30-day window and the date comparison will differ from the answer key.
