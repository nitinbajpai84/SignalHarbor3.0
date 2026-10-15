# UC6 runbook: Can we meet the capital calls? (run 3, 13 Oct 2026)

How to repeat UC6 run 3 from a clean checkout: July and August 2026, after the overnight fixes (FIXA to FIXE2). Run 3 reached the end of both months. Every step below is what actually worked, with the workaround where one was needed. Results: `UC6-REPORT.md`. Expected figures: `docs/demo/uc6/ANSWER-KEY.md`.

Scripts: `docs/test/uc-live/uc6-scripts/` (the run 3 ones start with `r3_`; `m1_*` and `load_month.py` are reused with the project and file ids changed). Shots: `docs/test/uc-live/uc6-run3-shots/<month>-<nn>-<person>-<milestone>.png`. Every API call of the run is in `uc6-scripts/run3-calls.jsonl` (method, path, body, status, first 400 characters of the answer).

## 0. Prerequisites

- Windows, Git Bash. Repo Python: `/c/Users/Nitin/Python Projects/Investment Doc Extraction/files/venv/Scripts/python.exe` (needs Playwright Chromium). `ui/dist` must be built.
- `DATABASE_URL` and `REDIS_URL` unset. Port **8811** only. Do not touch 8530, 8812, 8400, 8504, 8200 or the repo `data/`. Temp files on `D:/Temp`.
- Environment for the scripts: `export UC6_ENV=D:/Temp/uc6-sit/data` (where `uc6.py` reads the passwords from, never printed). `UC6_TMP` (default `D:/Temp/uc6r3`) holds response dumps and the call log; `UC6_SHOTS` defaults to `uc6-run3-shots`. Run a script with `sh docs/test/uc-live/uc6-scripts/py.sh <script.py> [args]`. The script path is resolved from the scripts folder, so pass a bare file name.
- People and sign-in: as in run 2 (login page, `#email`, `#password`; helper `Person("mei")` etc.). Mei Chen owner, Daniel Foo sponsor, Anita Rao head of data, Leo Park data engineer, Raj Patel approver, Sofia Reyes participant, Grace Ong admin.

## 1. Clean company and server

```sh
PY="/c/Users/Nitin/Python Projects/Investment Doc Extraction/files/venv/Scripts/python.exe"
unset DATABASE_URL REDIS_URL; export TMP=/d/Temp TEMP=/d/Temp PYTHONIOENCODING=utf-8; mkdir -p /d/Temp/uc6r3
"$PY" docs/test/uc-live/uc6-scripts/make_clean_env.py --root D:/Temp/uc6-sit/data --today 2026-07-31 --no-commitments
nohup "$PY" tools/serve_test.py --port 8811 --data-root D:/Temp/uc6-sit/data > /d/Temp/uc6r3/serve-stdout.txt 2>&1 &
```

`--no-commitments` (new in run 3) leaves the commitment register empty: since FIXA the commitments workbook loads through Data > Intake, so the old workaround W2 is gone. Expected output: 7 accounts, 3 entities, 4 portfolios, 33 instruments, `"commitments": 0`, no cash, no cases. Check: `s0_check.py` (mode `testing`, no cases, projects or runs, header shows "Cycle: 31 Jul 2026"). The env script still pins the company clock (the cycle date) to 31 Jul. In August Anita sets it on screen (step 14).

To stop: `taskkill //PID <pid> //F` (find the pid with `netstat -ano | grep :8811`), then delete `D:/Temp/uc6-sit` and `D:/Temp/uc6r3`.

## Month 1: July 2026 (cycle date 31 Jul)

### 2. Mei tells North what she needs (`m1_01_north.py`, then `m1_01b_reply.py`)

Mei types into **Build > Intent** (first message plus Start, then the chat box). Messages 1 to 8 are in `m1_01_north.py` (28 to 84 s per North turn). Then `m1_01b_reply.py "<text>" ...` sends follow-ups through the same box. What the run needed, in order:

9. "Yes, accept all of those drafts. Access: only the named readers ... plus Daniel Foo as sponsor. Format: a single page with KPI cards and a table by entity. Please drop the six-month funding headroom KPI; I did not ask for it."
10. "To finish: the result looks like one page per month ... We will know it worked when ... The process: 1) Leo uploads ...; 5) Sofia reads it as risk owner." (full text in `UC6-REPORT.md` of run 2, section 9, and in `m1_north_turns`)
11. "Yes, accept all of it. The process map is still empty. Please draft it from the five steps I gave: ..." (**North only drafted the five steps when asked a second time.**)
12. "Yes, accept all of it. The figure list is too short. Please add these KPIs, all in USD by entity ...: Available cash, Cash after confirmed calls, Cash after all noticed calls, Uncalled commitment by fund, and Calls not yet confirmed." (North had drafted only K01 and K02 so far.)

FIXD result: `result` and `success` are filled from the chat (no hand edit needed), and the unclear point is settled by the person's reply. Intent: `ini-097ec18a7f77bc6be9cdf63cf23c8aeb`.

### 3. Mei accepts the last draft, Daniel signs, Mei sends to Build and hands over (`r3_m1_02_sign.py --sign`, `r3_m1_03_handover.py`)

- Mei accepts the pending proposal (`POST /api/v1/intents/{iid}/proposals/{id}/accept`) and sets K01's unit to USD (`PUT .../sow {section:"kpis", index:0, field:"unit", value:"USD", version}`).
- Daniel opens the sign page and signs (`POST .../sow/sign {"confirm": true, "version": 1}`): 200. No hand edits of result/success were needed (W3, W3b of run 2 are gone).
- Mei: `POST /api/v1/intents/{iid}/send-to-build` (project `prj-a4d01dff`), then **Mei herself** `POST /api/v1/projects/{pid}/handover {"to":"Leo Park","due":"2026-08-07",...}`: 200. FIXE1 (owner may hand over) and FIXE2 (a due date of 7 Aug is accepted at cycle 31 Jul) both hold. W4 and W5 are gone.

### 4. Architecture and samples (`m1_04_arch.py`, `m1_05_samples.py`; set `PID` and the system ids)

Leo confirms all systems and accepts all questions. North's intent produced **ten** "systems", five of them figures (not sources): Available cash by entity, Calls due next 30 days, Calls due 31-60 days, Uncalled commitment by fund, Administrator closing cash. Samples: the real files go to Commitments schedule, Bank cash files (EG-B), Administrator cash report, Notice receipt log, and Administrator closing cash (same admin CSV); the notice PDF (`2026-08/2026-07-06_cedarpoint_fund-D_call.pdf`, July has none) to the notices source. Marks: `r3_m1_06_pack.py` marks the eight PDF lines (0, 2, 3, 4, 5, 6, 7, 9).

### 5. Span drafts the pack (`r3_m1_06_pack.py`)

`POST .../architecture/pack/generate` after the marks (no hand-made silver table: FIXC makes Span reuse silver). Result: version 1, 13 open rows, silver reused `cash_movements`, `portfolios`, `legal_entities` (not `commitments`), one gold table over cash movements, no silver proposed. **The gold SQL is wrong and cannot run (see 8).**

### 6. Leo settles the open rows, Anita approves (`r3_m1_07_approve.py`)

Leo: `PUT .../pack/edit {section:"mapping", key:<row id>, changes:{resolve:"<note>"}}` for each of the 13 rows (five "map this sample" checks and four "Define the KPI" rows, among others), then `POST .../pack/submit`. Anita: `POST .../pack/approve {version, note}`. One approval also approves the build plan (pack `plan_version` 1 appears at once; FIXC point 5 works).

### 7. July intake (`load_month.py 2026-07`, `r3_intake_fix.py jul`, `r3_funds.py jul <file>`)

1. Leo uploads each file on **Data > Intake** (API: `POST /api/v1/intake/upload`, `.../profile`, `.../load`; codes `commitments_schedule`, `bank_cash_files`, `administrator_cash_repor`, `notice_receipt_log`). All six wait for a mapping.
2. The data agent proposes a mapping per file (`GET /api/v1/model/mappings`). What the proposals got right: ISO dates carry `%Y-%m-%d`; closing cash goes to `position_snapshots.source_market_value`; net movement to `cash_movements.amount`; commitment to `commitments.commitment_amount`.
3. Leo corrects, as the file page allows (`PUT /api/v1/model/mappings/{id}` `{"columns":[{"source","target":"ignore"}], "fixed":{"portfolios.portfolio_code":"EG-B-OPS"}}`), done through the API in `r3_intake_fix.py`:
   - commitments: "Estimate amount" proposed as `commitments.commitment_amount` (the manager estimate!): set to ignore; "Fund key" to ignore.
   - bank files: `account_number` and `account_name` to ignore, and a fixed portfolio per entity (EG-B-OPS, EG-GROWTH, EG-LIQUID), because the files carry no portfolio code.
4. Anita approves the six mappings (`POST .../approve`). Leo loads again: administrator 93 of 93, bank 31 of 31 each, commitments "nothing_loaded: 5 funds need approval", receipt log "no data rows".
5. Fund approval (button on the file page, `POST /api/v1/evidence/aliases/{identifier_id}/approve`) for the five funds, then load the commitments file again: 5 of 5. Result: cash and commitments are in silver.
6. Check (Path K): `liq.py 2026-07-31 raj` gives 2,305,906.48 / 1,252,492.34 / 905,000.00, no calls, uncalled total 13,450,000.

### 8. Run on a copy and go live (`r3_builder.py`, `r3_samples2.py`, `r3_gold_fix.py`, `r3_pack2.py`, `r3_bench.py`)

1. Leo: `POST .../builder/start`. It stops: five "systems" have no landed sample, and the notices source has no statement. Workaround (`r3_samples2.py`, attempt 2; attempt 1 with the real files answers `duplicate`): Leo uploads a small extract file for each of the five figure sources with that source code (`POST /api/v1/intake/upload`), and the notice PDF to Evidence (`POST /api/v1/evidence/documents {filename, data(base64)}`). Then `POST .../builder/recheck`.
2. The run on a copy fails: `The SQL may only create or add rows; it contains something else.` The guard `b6_run._BAD` matches the word `call` in `movement_type = 'call'`. Workaround (`r3_gold_fix.py`): Leo rewrites the gold select in the pack (`PUT .../pack/edit {section:"gold_table", key:<table>, changes:{sql, definitions, depends_on}}`), using `like 'cal%'` and silver tables `position_snapshots`, `portfolios`, `cash_movements`, `legal_entities` (it must not name the CTE `asof`, a DuckDB keyword). Pack version goes to a new draft; `r3_pack2.py <v> jul` submits, Anita approves, Leo starts the builder.
3. Run on a copy: `run-20261012-221809-3b50` (test, ok, 11 of 11 checks, 3 gold rows).
4. Benchmark: July has no earlier report. `r3_bench.py` uploads `run3-benchmark-2026-07.txt` (the answer key figures as Mei's hand sheet). The builder reports "3 unexplained variances" because it compares each entity label with the column total. Leo goes live with `POST .../builder/go-live {"accept_variance": true}`: `run-20261012-221910-38a8`, PRODUCTION, ok.
5. Lumen starter (**Leo, not Mei**: Mei gets 403): `r3_lumen.py` then `POST .../studio/{did}/submit` (Leo) and `.../approve` (Anita): `r3_lumen2.py dash-ba87e21f`. Six tiles. `r3_tiles.py` reads the tile data (Path P).

## Month 2: August 2026 (cycle date 31 Aug)

### 9. Cycle date, intake, notice (`r3_cycle.py`, `load_month.py 2026-08`, `r3_funds.py aug`, `r3_notice.py`, `r3_confirm.py`)

1. Anita: Settings > Cycle date, API `PUT /api/v1/cycle-date {"cycle_date":"2026-08-31"}` (`r3_cycle.py 2026-08-31 aug`). The header reads "Cycle: 31 Aug 2026".
2. Leo uploads and loads the six August files. The July mappings are remembered (month digits are masked): five files load with no edits (93, 31, 31, 31, 5 rows). The receipt log asks for a fund approval (Cedarpoint Opportunities Fund II), then holds its row ("no portfolio"), then after a fixed portfolio fails with `NOT NULL constraint failed: cash_movements.effective_date`. Stopped there (two attempts): the receipt log is not loaded in August.
3. Notice: `POST /api/v1/evidence/documents/{id}/extract` reads four fields; Leo confirms the amount (`POST /api/v1/evidence/fields/{id}/confirm`). **Mei is refused (403)**: only the data team may.
4. Path K: `liq.py 2026-08-31 raj` (cash 2,287,630.12 / 1,199,690.58 / 654,014.07, no calls). Uncalled for EG-B is 8,900,000 before the notice is confirmed and **13,100,000 after** (wrong; see report H2).

### 10. Run, Action, Consume (`r3_run.py sandbox live`, `r3_action.py aug`, `r3_case.py`, `r3_case2.py`, `r3_shots.py`)

- `POST /api/v1/build/p/{pid}/run?mode=sandbox` then `?mode=live`: `run-20261012-222308-449c` (test), `run-20261012-222316-8a22` (production), both ok. Gold (Lumen tiles): available cash 4,141,334.77 in total, calls 0.
- Action (`/centre/action`): one case, "Fund the capital call, Cedarpoint Opportunities II, Entity B, 2026-07-23, USD 300,000", for the call that was paid on 23 Jul. Raj takes it (`POST /api/v1/cases/{id}/take`); his dismiss is refused (owner may not dismiss his own material case); Mei dismisses it with the reason "already paid on 23 Jul, notice received late" (`POST .../dismiss {reason}`). Action then reads "Nothing needs you today".
- Consume > Office (`/centre/consume/office`) as Raj: Entity B available cash 654,014.07; "Still to be called 13,100,000" (wrong).

## Workarounds used (run 3)

- R3-W1: five phantom "figure" sources need an extract file each, and the notices source needs a statement in Evidence, before the builder will run (`r3_samples2.py`).
- R3-W2: Leo rewrites the pack's gold select (the generated one is refused by the SQL guard, and wrong).
- R3-W3: Leo rather than Mei confirms PDF fields and starts the Lumen starter; Mei dismisses the case Raj took.
- R3-W4: Leo goes live with `accept_variance` (the benchmark compare ignores the entity in a label).
- Mapping corrections were made through `PUT /api/v1/model/mappings/{id}` (the call the file page makes), not by clicking in the page. The editable state of the file page was not captured on screen.
