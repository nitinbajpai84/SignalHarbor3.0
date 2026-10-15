# UC5 live test plan: Are we inside our limits?

Allocation and limit monitoring for Evergreen Office, run as a real person would run it: one build month (July 2026), then three monthly cycles (August, September, October). Synthetic data only. Evergreen Office and its people are the demo company; use no other names.

- Answer key: `docs/demo/uc5/ANSWER-KEY.md`. Sources: `docs/demo/uc5/sources/<YYYY-MM>/`.
- Status: plan only. No product code (`sh_platform/`, `ui/src/`) is edited. No commit, no push. The repo `data/` folder and ports 8400, 8504, 8200 and 8697 are not used.
- Temp files, screenshots and saved JSON go to `D:/Temp/uc5/`. The tester's own data root is `.sh-tmp/testenv/uc5/`.
- Each step names who does it, the route or on-screen label, the input, the expected result and what to record. Labels are the ones in `ui/src` at the time of writing. Where a label is not in the code, the step gives the API call instead.

---

## 0. Read first: what this plan corrects (checked against the code and the files)

The earlier draft had these errors. Each is fixed below.

| # | Earlier draft said | What the code and files actually show | Effect on the run |
|---|---|---|---|
| C1 | Seeded rule register holds the single-name cap at 6.00%, or unknown | `docs/test/10uc_universe.json` rules, loaded by `tools/seed_10uc.py`: `limit_single_name_liquid` max **5.00%**, effective **1 Jan 2026**, approved by Daniel Foo | Under the seed, July Harborview (5.73%) is a **real breach**. The key says inside at 6.00%. This is planted issue 1 showing in the product. Gate G1 must be decided before M1-19. |
| C2 | Seed starts clean | `tools/seed_10uc.py` `_checks()` runs the limits check as of **9 Oct 2026** and opens cases. The seeded warehouse already holds limit cases dated 9 Oct | The tester starts with limit cases that are not in the answer key. Record them at M1-03 and do not count them as July results. Gate G2. |
| C3 | Sofia Reyes takes and closes cases | Seeded role for Sofia is **participant** (credentials file). `e4a.permissions.yaml`: a participant may read, ask and note; **not** take, assign, submit, approve, resolve or dismiss | Sofia cannot do the risk-owner steps as seeded. Gate G3: Grace sets her role to owner, or Mei is the case owner, and the refusal is recorded as a finding. |
| C4 | Mei Chen is an owner | Credentials file says analyst. `ROLE1` says seeded environments move Mei to **owner** (`seed_evergreen.accounts()`). Check in Settings | Record the role seen in Settings; it decides which case buttons Mei sees. |
| C5 | Positions footer matches the latest-known totals (EG-B-OPS 22,525,000; EG-FUNDS 22,443,002) | The **Positions** sheet footer (rows 38 to 41, label "Portfolio totals") holds the **administrator** totals: EG-LIQUID 39,819,400; **EG-B-OPS 22,670,000**; **EG-FUNDS 22,697,833**. The latest-known values (22,525,000 and 22,443,002) come from the **Latest statements** sheet | A control-total check against the footer for EG-B-OPS and EG-FUNDS will not match the answer key's latest-known basis. Record the basis the product uses (Gate G4). Do not call it a pass. |
| C6 | Positions header is row 1 | Positions: title block rows 1 to 8, **header row 9**, data rows 10 to 36, totals rows 38 to 41. Latest statements: **header row 7**, data rows 8 to 14, no footer | Profiling must skip the title block. A profile that cannot find row 9 or row 7 is a finding. |
| C7 | Load writes the file straight away | `e0c_load` loads only with an **approved mapping** for that file name and sheet. With none, the load returns `waiting_for_mapping` with a `proposal_id` and writes nothing. A person who did not propose the mapping must approve it (`e0b_mappings._who_may_decide`) | Two loads per file in month 1: the first returns waiting for mapping, then the mapping is approved, then load again (M1-15 to M1-17). |
| C8 | Recon run is `/api/v1/recon/limits/run` | Confirmed: `POST /api/v1/recon/{code}/run` with `{as_of_date, cutoff?}`; code `limits` (`e3b_routes.py`) | Correct as written. The Action screen's **Run now** sends only the as-at date (`ReconPage.tsx`); **cutoff can only be set by the API** (Gate G6). |
| C9 | A test or production split on recon runs | Recon runs have **no** test or production field (`e3_recon.run_detail`). The Test and Production split is on pipeline runs (`b6_run`, `GET /api/v1/build/p/{pid}/runs`) and on Operations (`GET /api/v1/ops/runs?mode=test|production`) | Record as a gap: a limits run cannot be marked as a test run. |
| C10 | Cases are deduplicated across months | Limit case titles are `Limit breached · <name> · <portfolio> · <date>` (`e3_recon.py`). Dedupe is by **title**, so a standing breach in August is a **new** case titled 31 Aug. Only a same-day rerun reuses the case | The answer key expects a note, not a second case, in August. The product will open one. Record it as a finding (noise), not a pass. |
| C11 | Early warning at 0.25 points | No early-warning line exists in the product (`e3_recon.py` has none). The 0.25 band is only in the generator, `tools/make_uc5_data.py` | Expect no early-warning flag in any month. Record it as **missing**, not as a band error. |
| C12 | Hedge funds estimate flag | `e3_recon.py` has no estimate flag. October H1 and H2 are manager estimates (key, planted issue 9) | Expect no flag. Record it as **missing** if so. |
| C13 | Tolerance is 1 USD and 0.01 points | Key shares are rounded to 2 dp, so the product's over-by can differ by a few hundred USD | Tolerance: share within 0.01 point; over-by within USD 500. Larger is a wrong number. |
| C14 | Fund D is 192 days old at 30 Sep (seed fixture note) | 31 Mar to 30 Sep 2026 is **183 days** (the key). The seed's note text in `docs/test/10uc_universe.json` says 192 | Record which figure the product shows. A figure of 192 is a wrong-number finding in the seed text. |
| C15 | Routes for sign, consume and delivery | Intent sign is under the SOW router: POST `/api/v1/intents/{iid}/sow/sign` (`i4_routes.py`). The consume dashboard view has no project id: GET `/api/v1/consume/dashboards/{did}/view` (`cx_routes.py`). Delivery channels are under `/api/v1/build/p/{pid}/delivery/channels/{cid}` (`d1_routes.py`) | Routes in section 5 are corrected to these. |

---

## 1. Gates to decide before the first step

Each gate has a default. Record the decision and the person who made it at M1-00 in the run log. The tester does not decide a gate alone.

| Gate | Question | Who decides | Default in this plan | What to record |
|---|---|---|---|---|
| G1 | Which single-name cap is signed for January to August: 5.00% (register and universe) or 6.00% (`limits_signed_v1_2026-01-02.xlsx`, "Effective from 2026-01-01")? | Daniel Foo (CIO signs limits), with Anita Rao | **6.00% for Jan to Aug**, because the signed workbook is the signed document. The register gets a new approved version effective 1 Jan 2026 (M1-19). The 5.00% version stays in the history. | The decision, the version id in force on 31 Jul, and the July result the product shows |
| G2 | Accept the seeded starting state (9 Oct limit cases, 5.00% register, universe valuations for Jul to Sep)? | Anita Rao | Yes. The starting state is recorded, not cleaned. Nothing is deleted (no delete API exists for cases or rules). | The starting counts from M1-03 |
| G3 | Sofia Reyes is a participant. Can Grace Ong set her role to owner for this test? | Grace Ong (company admin) | Yes, set to owner in Settings > People (M1-04). If the screen cannot change roles, Sofia stays participant and Mei is the case owner. The gap is recorded. | Sofia's role before and after; whether a role-change screen exists |
| G4 | Control totals: which basis does the product check against? | Anita Rao | Record what the product shows for each footer total (administrator basis: EG-B-OPS 22,670,000 and EG-FUNDS 22,697,833) and whether the latest-known totals appear anywhere. Do not force a pass. | The control-total lines shown for each portfolio |
| G5 | Seeded valuations for Jul to Sep already exist (universe `valuations_monthly`). Loading the same month's file adds rows. | Leo Park (data engineer) | Count `valuation_observations` before the first load and after each load (M1-18). Same-date rows for the same instrument and portfolio are a finding if the limit figure changes. | The before and after counts per file |
| G6 | The Action Run now screen has no cutoff field. The answer key uses a cutoff (the receipt time). | Anita Rao | Monthly runs use the Run now screen (the real path). Each month the tester also runs the same check by API with the cutoff from the key (the proof run). Both are recorded. | Each run's id and figures from both paths |

---

## 2. Start the tester's own server (port 8812, own data root)

Run in Git Bash from the repo root. Keep temp files on `D:/Temp`.

```sh
cd "/d/Projects/01-Project Signal Harbor/Repo 1.0"
unset DATABASE_URL REDIS_URL SH_ALLOW_REAL_MODE
export TMP=/d/Temp TEMP=/d/Temp TMPDIR=/d/Temp
mkdir -p .sh-tmp/testenv/uc5 /d/Temp/uc5
```

Use the same Python interpreter as `.sh-tmp/uc4w/py.sh` (open that file to see its path). Below, `PY` stands for that interpreter.

1. Seed a fresh private data root (never `data/`):

```sh
PY tools/seed_demo_boot.py --reset --data-root ".sh-tmp/testenv/uc5/data"
```

Record the `demo-ready` lines. Credentials go to `.sh-tmp/testenv/uc5/data/_control/seed_credentials.txt`. Never print or copy the passwords.

2. Start the server in the background (scheduler off by default):

```sh
PY tools/serve_test.py --port 8812 --data-root ".sh-tmp/testenv/uc5/data" > /d/Temp/uc5/serve.out 2>&1 &
```

The server log is `.sh-tmp/testenv/uc5/server.log` (written by `serve_test.py`). Read it when a step fails. Do not watch the console.

3. Health check (must print 200):

```sh
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8812/login
```

4. Mode check: sign in as Daniel (section 3). The line under the agent name must read **Testing models (free tier)** (`ui/src/v1/router/ModeLine.tsx`). If it says **Real-use models**, stop and switch to Testing before anything else. Real use is never used in this test.

5. Stop the server at the end of the run only. Find the PID listening on 8812 with `netstat -ano | findstr :8812` and stop only that PID.

Leave the server up across all four months. Restart only after a `--reset`, with the same two commands.

---

## 3. People and sign-ins

Sign-ins come from the seeded credentials file. Emails follow `<first>.<last>.evergreen@example.test`. The tester reads each password from the file and types it into the sign-in form. Never write a password into the run log, the chat or this plan.

| Helper key | Person | Seeded role (credentials file) | Role used in this test | Used for |
|---|---|---|---|---|
| `daniel` | Daniel Foo | sponsor | CIO: signs the intent and limit versions; approves the dashboard and the delivery channel | M1-06, M1-19, M1-26, M1-27, M2-07 |
| `mei` | Mei Chen | analyst in the file; owner in a fresh seed (ROLE1; confirm in Settings) | Business owner: writes the intent; chases statements; case notes | M1-05, M1-28, M2-05, M3-03, M4-04 |
| `raj` | Raj Patel | approver | Approves a trim that cures a breach | M3-03, M4-04 |
| `sofia` | Sofia Reyes | participant (G3) | Risk owner: decides each breach real or stale; takes and resolves cases | M1-28, M2-05, M3-03, M4-04 |
| `anita` | Anita Rao | analyst plus head_of_data | Head of data: approves the pack, the plan, the mapping and go-live | M1-11, M1-12, M1-16, M1-24 |
| `leo` | Leo Park | analyst | Data engineer and operations: uploads, loads, runs, checks, goes live | M1-13 to M1-25, M2-01 to M2-04 |
| `grace` | Grace Ong | company_admin | Administrator: role changes (G3), access checks | M1-03, M1-04, M4 end check |

Rules:
- One browser context per person (a separate session each). The helper in section 4 does this.
- Sign out at the end of each person's turn (account menu, Sign out).
- Check the name at the top right after each sign-in.

---

## 4. How the steps are driven, and what is recorded

Two ways, in this order of preference:

1. **The product's own screen** (a real person's route). Use the label in the step.
2. **The same HTTP API the screen calls**, as the signed-in person. Use it where the step says "API", or where the screen does not offer the action. Record the call and the response.

Browser helper: copy `.sh-tmp/uc4w/lib.py` to `.sh-tmp/testenv/uc5/uc5lib.py` and change three things: `BASE = "http://127.0.0.1:8812"`, the credentials path to `.sh-tmp/testenv/uc5/data/_control/seed_credentials.txt`, and the screenshot folder `OUT` to `D:/Temp/uc5/shots`. The helper signs in through `/login` (fields `#email`, `#password`, then Enter). `W(who).api(method, path, body)` sends the same `X-CSRF-Token` header the UI sends. Playwright (headless Chromium) is what the repo already uses.

Run record: one row per step in `docs/test/uc-live/UC5-RUN-LOG.md` (the tester creates it):

| Step | Month | Person | Screen or API | Input | Expected (key or code) | Actual (screen text or response excerpt) | Run ID and figures | Result | Screenshot |
|---|---|---|---|---|---|---|---|---|---|

Result is one of: **pass**, **fail**, **wrong number** (outside tolerance), **missing** (no screen or no flag), **unclear** (a real person would not know what to do), **blocker**, **note**.

---

## 5. Route map (checked against the code)

| Action | Who (seat) | Method and route | Body |
|---|---|---|---|
| Health | any | GET `/login` | none |
| Start a project | Mei (business owner) | UI `/centre/build` > button **New project** > `/centre/build/new` > text box > **Start** | the message in M1-05 |
| North chat on an intent | the writer | POST `/api/v1/intents/{iid}/chat` | `{text}` |
| Sign the intent | sponsor | Open the intent's sign step (screen **Sign intent**, tick "I have read all"). API: POST `/api/v1/intents/{iid}/sow/sign` | per screen |
| List projects | any | GET `/api/v1/build/projects` | none |
| Architecture summary | Leo | GET `/api/v1/build/p/{pid}/architecture/summary` | none |
| Confirm systems | Leo | POST `/api/v1/build/p/{pid}/architecture/systems/confirm` | per screen |
| Sample file for a source | Leo | POST `/api/v1/build/p/{pid}/architecture/samples/{sid}/table` (multipart) | file |
| Mark fields on a sample | Leo | POST `/api/v1/build/p/{pid}/architecture/samples/{sid}/mark` | fields |
| Span questions | Leo | GET `.../architecture/questions`; POST `.../architecture/questions/accept-all` | none |
| Generate pack | Leo | POST `.../architecture/pack/generate` | none |
| Submit pack | Leo | POST `.../architecture/pack/submit` | none |
| Approve pack | Anita (head of data) | POST `.../architecture/pack/approve` | none |
| Propose plan | Leo | POST `/api/v1/build/p/{pid}/plan/propose` | none |
| Approve plan | Anita | POST `/api/v1/build/p/{pid}/plan/approve` | none |
| Upload a file | Leo, Grace | UI `/centre/data/intake` > **Upload a file**. API POST `/api/v1/intake/upload` (multipart: `data`, `filename`, `source_code`, `sensitivity`) | file; `source_code` = `administrator_positions` or `limits_signed`; `sensitivity` = `internal` |
| List uploaded files | Leo | GET `/api/v1/intake/files` | none |
| Profile a sheet | Leo | POST `/api/v1/intake/files/{file_id}/profile` | `{"sheet": "Positions"}`, then `{"sheet": "Latest statements"}`, or `{"sheet": "Signed limits"}` |
| Load a file | Leo | POST `/api/v1/intake/files/{file_id}/load` | none |
| List mappings | data team | GET `/api/v1/model/mappings` | none |
| Read a mapping | data team | GET `/api/v1/model/mappings/{mapping_id}` | none |
| Approve a mapping | Leo or Anita (not the proposer) | POST `/api/v1/model/mappings/{mapping_id}/approve` | none |
| Propose a limit version | Leo | POST `/api/v1/rules/{rule_code}` | `{definition_text, parameters, effective_from, rule_type: "limit"}` |
| Approve a limit version | Daniel (sponsor) | POST `/api/v1/rules/versions/{vid}/approve` | none |
| Rule history | any | GET `/api/v1/rules/{rule_code}/history` | none |
| Rules register | any | GET `/api/v1/rules` (UI: Settings > Rules, `/centre/settings/rules`) | none |
| Instruments and asset class | Leo | GET `/api/v1/instruments` (setting a class is not done in this test; see M4-04) | none |
| Builder start | Leo | POST `/api/v1/build/p/{pid}/builder/start` | none |
| Builder recheck | Leo | POST `/api/v1/build/p/{pid}/builder/recheck` | none |
| Benchmark | Leo | POST `/api/v1/build/p/{pid}/builder/benchmark` | `{report_version_id}` for a signed report, or `{name, text}` for a plain-text report |
| Go live | Leo (approved by Anita) | POST `/api/v1/build/p/{pid}/builder/go-live` | `{"no_benchmark": true}` when there is none; `{"accept_variance": true}` only after a decision |
| Send back | Leo | POST `/api/v1/build/p/{pid}/builder/send-back` | `{reason}` |
| Pipeline run (copy, then live) | Leo | POST `/api/v1/build/p/{pid}/run`; list GET `/api/v1/build/p/{pid}/runs` | the body the screen sends (record it; this plan does not fix it) |
| Operations and run IDs | Leo | GET `/api/v1/ops/runs?mode=test` or `?mode=production`; UI `/centre/operations` (section **Runs**, badge TEST or PRODUCTION) | none |
| Limits check | Leo (full access to a portfolio) | UI `/centre/action/reconciliations` > limits card > **Check as at** (date) > **Run now**. API POST `/api/v1/recon/limits/run` | `{"as_of_date": "2026-07-31", "cutoff": "2026-08-04T06:00:00Z"}` |
| Recon runs | any | GET `/api/v1/recon/runs` | none |
| Cases list | any | GET `/api/v1/cases?exception_type=limit_breach` (UI `/centre/action/cases`) | none |
| Case detail | any | GET `/api/v1/cases/{cid}` | none |
| Take a case | owner, approver, analyst, sponsor, admin (not participant) | POST `/api/v1/cases/{cid}/take` (UI label **Take the case**) | none |
| Assign | same | POST `/api/v1/cases/{cid}/assign` | `{to, note}` |
| Note | everyone who can see the case | POST `/api/v1/cases/{cid}/note` | `{text}` |
| Ask finance | everyone who can see the case | POST `/api/v1/cases/{cid}/ask_finance` | `{to}` |
| Approve a case action | approver, owner, analyst | POST `/api/v1/cases/{cid}/approve` | `{rationale}` |
| Resolve | owner, approver, analyst, sponsor, admin | POST `/api/v1/cases/{cid}/resolve` | `{code, note}` |
| Dismiss | same | POST `/api/v1/cases/{cid}/dismiss` | `{reason}` |
| Starter dashboard (Lumen) | Leo | POST `/api/v1/build/p/{pid}/studio/starter` | none |
| Accept starter tiles | Leo | POST `/api/v1/build/p/{pid}/studio/{did}/starter/accept` | none |
| Submit / approve dashboard | Leo / Daniel | POST `/api/v1/build/p/{pid}/studio/{did}/submit`; POST `.../studio/{did}/approve` | none |
| Delivery channel | Leo / Daniel | POST `/api/v1/build/p/{pid}/delivery/channels` (create); POST `.../delivery/channels/{cid}/submit`; `.../approve`; `.../send-back`. Delivery go-live: POST `/api/v1/build/p/{pid}/delivery/go-live` | per screen |
| Consume: list dashboards | Daniel | GET `/api/v1/consume/p/{pid}/dashboards` | none |
| Consume: open dashboard | Daniel | GET `/api/v1/consume/dashboards/{did}/view` | none |
| Consume: tile "why" | Daniel | GET `/api/v1/consume/p/{pid}/dashboards/{did}/tiles/{tid}/why` | none |
| Row counts per table | Anita, Leo | GET `/api/v1/centre-map/model` (UI: Map > Data model) | none |
| Model proposals | Anita | GET `/api/v1/model/proposals`; POST `/api/v1/model/proposals/{n}/approve` | none |

Permission note: a route a person may not call returns 403 with a plain message. A 403 on a step the person needs is a finding. Record the message text.

---

## 6. Month 1 (July 2026): the full build

Sources: `docs/demo/uc5/sources/2026-07/administrator_positions_2026-07-31.xlsx` and `docs/demo/uc5/sources/2026-07/limits_signed_v1_2026-01-02.xlsx`. Received by the company 4 Aug 2026 06:00 UTC. The key's July row is the expected result.

### M1-00 Gates
Decide G1 to G6 (section 1). Record each with the name of the person who decided it. If G1 is not decided, stop: the July result cannot be checked.

### M1-01 Health and mode (tester)
1. Run the health check (section 2, step 3). Expected: `200`.
2. Sign in as Daniel (section 3). Expected: "Testing models (free tier)" under the agent name. Screenshot `uc5-01-mode`.

### M1-02 Sign-in check (each person)
1. Sign in as each of the seven people in turn. Confirm the name at the top right and record the Settings items that appear. Expected per ROLE1: Mei, Daniel and Sofia see three Settings items; Raj four; Anita seven; Leo eight; Grace sixteen. Record any difference.

### M1-03 Starting state (Grace)
1. Sign in as Grace. Open `/centre/settings/rules`. Record the four limit rules: `limit_single_name_liquid` 5.00 from 1 Jan 2026; `limit_listed_equity_liquid` 60 to 90 on EG-LIQUID; `limit_manager_entity_b` 0 to 55 on EG-B-OPS; `limit_hedge_funds` 20 to 60 on EG-FUNDS.
2. API: GET `/api/v1/rules`. Record the full list. Then GET `/api/v1/rules/limit_single_name_liquid/history`.
3. API: GET `/api/v1/cases?exception_type=limit_breach`. Record every case: id, title (with its date), status, owner. Expected from the seed: cases dated 9 Oct 2026. Confirm from the list; do not assume.
4. API: GET `/api/v1/instruments`. Record the instrument with no asset class (Pacific Rim Convertible 2029 note, expected).
5. API: GET `/api/v1/centre-map/model`. Record the row counts for `valuation_observations` and `position_snapshots`. This is the **before** count for G5.
6. Screenshots `uc5-02-starting-rules` (the rules screen) and `uc5-03-starting-cases` (`/centre/action/cases`).

### M1-04 Roles (Grace)
1. Open Settings > People and access (the section named in ROLE1; if the label differs, record the label you see). Find Sofia Reyes. Record her role.
2. If Sofia is participant and G3 says owner: change her role to owner with the screen. Record whether the screen allows it. If there is no screen, record "missing: no role change in the UI" and carry on with Mei as the case owner.
3. Sign Grace out.

### M1-05 Intent with North (Mei)
1. Sign in as Mei. Open `/centre/build`. Click **New project**. Expected: `/centre/build/new` opens with one text box.
2. Type this in one message and click **Start**. Copy the text exactly:

   > Monthly limit monitoring for Evergreen Office. Each month, when the administrator's month-end positions arrive, check the portfolios EG-LIQUID, EG-B-OPS and EG-FUNDS against the signed investment limits. For each limit show the exposure as a percentage of its portfolio, the maximum, the headroom in percentage points, and whether it is inside, in breach, or in breach with stale inputs. Show each breach as real or stale. List instruments with no asset class as questions. Readers: Sofia Reyes (risk owner), Mei Chen, and Daniel Foo (CIO, who signs). The work is ready by the 5th business day. Sources: the administrator month-end positions workbook (sheets Positions and Latest statements) and the signed limits workbook (sheet Signed limits), both uploaded by hand each month.

3. North asks questions one at a time. Answer each in the chat. For sources, answer "the two files, uploaded by hand". For grain, answer "per portfolio, month end". For readers, answer with the three names above.
4. Ask North for the closing summary. Record its text. Check: all four limit figures listed; both sources listed with how they arrive; the readers named; the asset-class question named. Record any "no source yet" line, and any wrong sign or unit in a definition (the walkthrough found a difference drafted in basis points). Screenshot `uc5-04-north-summary`.
5. Mark the intent ready when North offers it. Record the intent id from the URL (`iid`).

### M1-06 Sign the intent (Daniel)
1. Sign in as Daniel. Open the intent (`/centre/intent/{iid}`) and its sign step. Tick **I have read all**. Click **Sign intent**.
2. Expected: the intent is signed and read-only. Record the signed text and the date.
3. Check the definitions shown: headroom in percentage points (not basis points); exposure as a percentage of the portfolio total. A wrong sign or unit is a **wrong number** finding. Screenshot `uc5-05-signed-intent`.

### M1-07 Hand over to the data team (Mei)
1. Sign in as Mei. Hand the Architecture and Pipelines steps to Leo, due three working days after 31 Jul 2026 (record the date used), with a note listing the two files. If the product has no handover control, record "missing" and carry on: Leo signs in next.

### M1-08 Architecture summary (Leo)
1. Sign in as Leo. Get the project id: GET `/api/v1/build/projects` (the project from M1-05). Record `pid`.
2. Open `/centre/build/architecture`. API: GET `/api/v1/build/p/{pid}/architecture/summary`. Expected: the two sources from the intent, with format, channel and frequency already filled in from the intent (not asked again).
3. Confirm each source with the screen. Record any mismatch (file name, columns, host). Expected: none. If one appears, the intent value is shown beside it. Screenshot `uc5-06-architecture-summary`.

### M1-09 Samples and marked fields (Leo)
1. On the architecture page, upload the July positions workbook as the sample for the administrator source, and the July limits workbook as the sample for the limits source (API: POST `.../architecture/samples/{sid}/table`, with the `sid` from the summary).
2. Mark the fields on the positions sample (API: POST `.../samples/{sid}/mark`): portfolio, administrator code, instrument, instrument type, asset class, currency, quantity, market value (USD), valuation date, value status. On the Latest statements sheet: portfolio, administrator code, instrument, latest known value (USD), statement reference, valuation date, value status, days old.
3. Record the response for each call.

### M1-10 Span questions (Leo)
1. API: GET `.../architecture/questions`. For each question record the proposed default. Expected defaults: history type 2 for asset class and manager; freshness daily, and the fifth business day of the month for the monthly pack. Accept the proposed defaults: POST `.../architecture/questions/accept-all`. Record the list.

### M1-11 Pack generate, submit, approve (Leo, then Anita)
1. Leo: POST `.../architecture/pack/generate`. Read the target model. Expected: a gold table for limit headroom with exposure, maximum, headroom, result, stale flag and cause, plus the asset-class and manager dimensions. Record the table names; check none is cut off mid-word (walkthrough finding).
2. If Span proposes a new table or column, it appears as a model proposal: GET `/api/v1/model/proposals`. Record the number `n`. Anita approves it: POST `/api/v1/model/proposals/{n}/approve`.
3. Leo: POST `.../architecture/pack/submit`.
4. Anita (head of data) reads the pack. Check the grain (per portfolio, month end), the three measure definitions (exposure in percent of the portfolio total; headroom in points; cause: stale if an input is older than 90 days at the as-at date or not verified), and the table names. Then POST `.../architecture/pack/approve`. Record the pack version. Screenshot `uc5-07-pack-approved`.

### M1-12 Build plan (Leo, then Anita)
1. Leo: POST `/api/v1/build/p/{pid}/plan/propose`. Anita: POST `/api/v1/build/p/{pid}/plan/approve`. Expected: plan v1 approved, with the same tables as the pack. Record.

### M1-13 Upload the two July files (Leo)
1. Open `/centre/data/intake`. Use the control labelled **Upload a file** and choose `administrator_positions_2026-07-31.xlsx`. If the screen asks for no source code, record that and use the API for the source code: `curl -F "data=@<path>" -F "filename=administrator_positions_2026-07-31.xlsx" -F "source_code=administrator_positions" -F "sensitivity=internal" http://127.0.0.1:8812/api/v1/intake/upload`, with Leo's session cookie. The helper's `api()` is the simpler route.
2. Upload `limits_signed_v1_2026-01-02.xlsx` the same way with `source_code=limits_signed`.
3. Record each `file_id` from the response. GET `/api/v1/intake/files` lists them. Screenshot `uc5-08-intake-uploaded`.

### M1-14 Profile each sheet (Leo)
1. POST `/api/v1/intake/files/{file_id}/profile` with `{"sheet": "Positions"}`. Expected: the header is found on row 9 and the title block is skipped. Record the header row the profile reports.
2. Profile `Latest statements` on the same file (`{"sheet": "Latest statements"}`). Expected: header on row 7.
3. Profile `Signed limits` on the limits file. Expected: the Version cell reads v1 and the table starts at its header row. Record any failure: a title block that defeats profiling is a finding.

### M1-15 First load: waiting for a mapping (Leo)
1. POST `/api/v1/intake/files/{file_id}/load` for the positions file. Expected: `status: waiting_for_mapping`, reason `no_mapping`, a `proposal_id`, and "nothing was loaded". Record the response.

### M1-16 Approve the mappings (Leo or Anita, not the proposer)
1. GET `/api/v1/model/mappings`. Find the proposals by file name. Open each (GET `/api/v1/model/mappings/{mapping_id}`) and record the target table of each column. For the positions sheet the limit-relevant target is `valuation_observations` (portfolio, instrument, valuation date, value, currency, approval status). If the mapping sends positions only to `position_snapshots`, the limit check will not see the July values: record a **blocker** and stop the July run until a person decides the mapping.
2. The proposer is the data agent, so a data-team member may approve. Leo approves: POST `/api/v1/model/mappings/{mapping_id}/approve` for the positions sheet, the statements sheet and the limits sheet. Record each version.

### M1-17 Second load and control totals (Leo)
1. POST `/api/v1/intake/files/{file_id}/load` again for each file. Expected: rows loaded; the step report shows the control-total checks.
2. Record the check lines for each portfolio footer. EG-LIQUID 39,819,400.00 matches the footer. EG-B-OPS and EG-FUNDS footers are the **administrator** basis (22,670,000 and 22,697,833). Record the basis the product compares against, and whether the latest-known totals (22,525,000 and 22,443,002) appear anywhere (G4). A mismatch shown with its basis stated is a finding, not a load failure.
3. Record the number of checks run (expect three portfolio footer checks for the positions file) and the status the product shows.

### M1-18 Row counts after the load (Leo)
1. GET `/api/v1/centre-map/model`. Record the `valuation_observations` and `position_snapshots` counts.
2. Compare with M1-03 step 5. The difference is the July rows from the file. If July rows are already in the warehouse (universe history), the file adds rows for the same instrument, portfolio and date. Record the number of rows per instrument for 31 Jul, and whether the limit figure changes (it must stay within the tolerance in M1-22). A changed figure is a **wrong number** finding (G5).

### M1-19 Limit versions (Leo proposes, Daniel signs)
Read G1 first. Default (6.00% for January to August):

1. Leo proposes the signed v1 single-name cap, effective 1 Jan 2026 (the workbook says "Effective from 2026-01-01"):
   POST `/api/v1/rules/limit_single_name_liquid` with body:
   ```json
   {
     "definition_text": "EG-LIQUID: Harborview Semiconductor must be between 0% and 6% of the portfolio. Signed v1 (Daniel Foo, 2 Jan 2026), effective 1 Jan 2026.",
     "parameters": {"dimension": "single_name", "bucket": "Harborview Semiconductor", "min_pct": 0.0, "max_pct": 6.0, "portfolio_code": "EG-LIQUID"},
     "effective_from": "2026-01-01",
     "rule_type": "limit"
   }
   ```
2. The other three limit lines are already signed in the register. Check them against the v1 workbook (listed equity 60 to 90; Cedarpoint 0 to 55 on EG-B-OPS; hedge funds 20 to 60 on EG-FUNDS). Do not propose them again unless a value differs; record "unchanged".
3. Daniel approves the new version: POST `/api/v1/rules/versions/{vid}/approve` (`vid` from the step 1 response). Record it.
4. GET `/api/v1/rules/limit_single_name_liquid/history`. Expected: the 5.00% register version (1 Jan) and the new 6.00% version (1 Jan, a higher version number). The product uses the newest version effective on the date (`e3_rules.current`), so July uses 6.00%. Record which version the July run uses (the M1-22 response carries the rule version id).
5. If Daniel chooses the 5.00% register value instead (G1 other answer), record it, skip steps 1 to 3, and expect Harborview as a **real breach** in July. That result is a finding, not the answer key.

### M1-20 Instruments and asset class (Leo)
1. GET `/api/v1/instruments`. Expected: the Pacific Rim Convertible 2029 note has no asset class. Leave it blank. The limit run must put it in **questions** and in no bucket. Do not set a class in this test (the decision is in M4-04).

### M1-21 Run on a copy (Leo)
1. Start the builder: POST `/api/v1/build/p/{pid}/builder/start` (or the screen's start control on Build > Pipelines, `/centre/build/pipelines`). Record the response.
2. Run the pipeline on a copy (the test run): POST `/api/v1/build/p/{pid}/run` with the body the screen sends (record it), or the Test control on `/centre/build/pipelines`.
3. GET `/api/v1/build/p/{pid}/runs`: record the run id (format `run-YYYYMMDD-HHMMSS-xxxx`) and its mode. It must be a test run, not production. GET `/api/v1/ops/runs?mode=test`: the same id should appear. Check the steps and row counts.

### M1-22 Limits check on the copy (Leo)
1. Proof run by API first, so the figures are on file: POST `/api/v1/recon/limits/run` with:
   ```json
   {"as_of_date": "2026-07-31", "cutoff": "2026-08-04T06:00:00Z"}
   ```
   Save the JSON response to `D:/Temp/uc5/jul_limits_api.json`. Record `checked`, `breaks`, `opened`, and the `results` lines (exposure, maximum, headroom, result, cause, over-by).
2. Real-person run on the screen: open `/centre/action/reconciliations`. In the limits card set **Check as at** to `2026-07-31` and click **Run now**. The screen sends the as-at date only (G6). Record the figures and the run time. They must match step 1. A difference is a finding.
3. Expected results (key, July):

| Line | Figure | Max | Headroom | Result | Cause |
|---|---|---|---|---|---|
| Harborview Semiconductor (single name, EG-LIQUID) | 5.73% (2,283,600 of 39,819,400) | 6.00% | 0.27 | inside | - |
| Listed equity (EG-LIQUID) | 80.04% (31,870,300) | 90.00% | 9.96 | inside | - |
| Cedarpoint Ventures, C plus D (EG-B-OPS) | 57.38% (12,925,000 of 22,525,000) | 55.00% | -2.38 | **breach, over by 536,250** | **stale data**: Fund D valued 31 Mar, 122 days old |
| Hedge funds, H1 plus H2 (EG-FUNDS) | 54.49% (12,229,802 of 22,443,002) | 60.00% | 5.51 | inside | - |
| Question (no line, no case): Pacific Rim Convertible 2029 | 1,084,000 = 2.72% of EG-LIQUID | - | - | question: needs a class | - |

4. Expected cases: exactly **one** new limit case for July (Cedarpoint, stale data), titled with `31 Jul 2026`. Check GET `/api/v1/cases?exception_type=limit_breach`. Record whether the case is new (expected, since the seed's cases are dated 9 Oct).
5. Cedarpoint's numerator is Funds C plus D, with Fund C at the latest known 8,275,000 (amended statement), not the administrator's value. Record which value the product shows and whether it shows the 145,000 difference against the administrator figure (planted issue 11). Record "explained" or "not explained".
6. Early warning: none expected (C11). Record "not shown" as **missing**.

### M1-23 Benchmark (Leo)
1. The builder asks for a benchmark to check against. For July there is no earlier report, so the answer is "none". Record what the screen says when there is no benchmark. Expected per code: go-live refuses without a benchmark or an explicit "no benchmark" answer (409: "Give the builder a benchmark to check against first, or say there is none"). Record the text shown.

### M1-24 Go live (Leo, approved by Anita)
1. POST `/api/v1/build/p/{pid}/builder/recheck`. Record the result.
2. POST `/api/v1/build/p/{pid}/builder/go-live` with `{"no_benchmark": true}`. Record the response and the schedule set from the pack (fifth business day of the next month).
3. Anita approves the go-live on the screen (or records her approval). Record the approval text.
4. GET `/api/v1/build/p/{pid}/runs` and GET `/api/v1/ops/runs?mode=production`: record the production run id. It must differ from the test run in M1-21. Screenshot `uc5-12-operations-runs` after this step.

### M1-25 Production limits run for July (Leo)
1. Run the limits check again for the same as-at date (API or Run now, as in M1-22). Expected: the same figures (same data). Record the run id from GET `/api/v1/recon/runs`. Note in the record that recon runs carry no test or production mark (C9).

### M1-26 Starter dashboard (Lumen; Leo builds, Daniel approves)
1. Leo: POST `/api/v1/build/p/{pid}/studio/starter`. Record the dashboard id `did` and the tile list.
2. Expected tiles, from the intent's figures: the four limits with exposure and headroom; breaches by cause (one stale); the question count (1); the stale statement list. Check every tile: percentages read as percentages (not 0.0573); the trend axis is not in fractions; the tiles are readable on the dark theme. Record each tile's title and value. Walkthrough findings to re-test: a named figure with no tile; the same tile twice; white tile boxes on the dark theme.
3. Leo accepts the starter tiles: POST `/api/v1/build/p/{pid}/studio/{did}/starter/accept`. Then POST `/api/v1/build/p/{pid}/studio/{did}/submit`.
4. Daniel approves: POST `/api/v1/build/p/{pid}/studio/{did}/approve` (or the approval screen). Check the approval panel text "What Lumen checked". Expected: it names the run id and the check result. Walkthrough finding: the panel once said "No reviewed run is on record" after a passing check. Record the exact text. Screenshot `uc5-09-approval-panel`.

### M1-27 Delivery channel (Leo, then Daniel)
1. Leo: POST `/api/v1/build/p/{pid}/delivery/channels` for the readers in the intent. Then POST `/api/v1/build/p/{pid}/delivery/channels/{cid}/submit`. Daniel: POST `.../channels/{cid}/approve`. Then POST `/api/v1/build/p/{pid}/delivery/go-live`.
2. Open the preview on the delivery screen. Expected: figures shown as percentages. Walkthrough finding: raw fractions (0.0573) in the email preview. Record. Do not send any message. The outbox is simulated; record "not sent".

### M1-28 Action and cases (Sofia; Mei)
1. Sign in as Sofia. Open `/centre/action`. Expected, depending on G3:
   - If Sofia is owner (G3 done): the July Cedarpoint case is listed with a **Take the case** button. Click it. Record.
   - If Sofia is still participant: no take button; POST `/api/v1/cases/{cid}/take` returns 403 with its message. Record the message. This is a **finding** (the risk owner cannot act).
2. Sofia reads the case: GET `/api/v1/cases/{cid}`. Record the cause (stale data), the description (Fund D valued 31 Mar, 122 days old) and the over-by amount.
3. Sofia records the decision: POST `/api/v1/cases/{cid}/note` with `{"text": "Stale statement, not a real breach. Fund D 30 Jun statement requested."}`. Then POST `/api/v1/cases/{cid}/resolve` with `{"code": "stale_data", "note": "Stale statement, not a real breach. Fund D 30 Jun statement requested."}`. Record the status and resolution code. Screenshot `uc5-11-jul-case`.
4. Mei: sign in. Open the Fund D statement item in Action's "Statements to chase" group. Add a note (the screen, or POST `/api/v1/cases/{cid}/note`). No message is sent outside the product.

### M1-29 Consume (Daniel)
1. Sign in as Daniel. Open `/centre/consume`. GET `/api/v1/consume/p/{pid}/dashboards`. Expected: the July dashboard is listed under the project. Walkthrough finding: the approved dashboard did not appear in Consume. Record "shown" or "not shown".
2. Open the dashboard: GET `/api/v1/consume/dashboards/{did}/view`. Check the figures against M1-22. Screenshot `uc5-13-dashboard-consume`.
3. Open the Cedarpoint tile's "why": GET `/api/v1/consume/p/{pid}/dashboards/{did}/tiles/{tid}/why`. Expected: the run id and the rule version. Record.

### M1 end check (Daniel, Anita, Grace)
- Action: the July case closed with its reason (M1-28).
- Operations (`/centre/operations`, section Runs): the July test run and production run, each with a run id.
- Record the open decisions: G1 (limit version), G4 (control basis), G3 (role), the M1-23 benchmark answer, the NAV difference (planted issue 11), and the pack table names.

---

## 7. Month 2 (August 2026): receive, check against July, act

Sources: `docs/demo/uc5/sources/2026-08/administrator_positions_2026-08-31.xlsx` and `docs/demo/uc5/sources/2026-08/limits_signed_v1_2026-01-02.xlsx`. Received 2 Sep 2026 06:00 UTC. The limits file is unchanged (v1); a real person still re-uploads it and checks the register still holds v1.

### M2-01 Receive and load (Leo)
1. Upload both files again (M1-13) with new `file_id`s. Profile as in M1-14.
2. Load. The mappings are approved, so no waiting step is expected. Record the response and the check lines.
3. GET `/api/v1/centre-map/model`: record the `valuation_observations` count and the change from the July count (G5).
4. Key totals for August: EG-LIQUID 39,552,000.00; latest known EG-B-OPS 22,525,000 and EG-FUNDS 22,545,000. The answer key gives only the latest-known figures. Record the footer totals in the file and the basis the product checks against (G4).

### M2-02 Benchmark against July (Leo)
1. Save the July limits result as a plain-text report: from `D:/Temp/uc5/jul_limits_api.json`, write `D:/Temp/uc5/jul_limits_report.txt` with one line per limit (exposure, maximum, headroom, result, cause) and the Pacific Rim question. Use only the names in the answer key.
2. In the builder, give that text as the benchmark: POST `/api/v1/build/p/{pid}/builder/benchmark` with `{"name": "July 2026 limits report (go-live)", "text": "<file text>"}`. The screen equivalent is the benchmark upload control on Build > Pipelines. Record the response.
3. Expected variance by line (key): Harborview 5.73% to 5.71%; listed equity 80.04% to 80.06%; Cedarpoint 57.38% unchanged (same stale input); hedge funds 54.49% to 54.56%. No line should move by more than the holdings explain. Record the variance table as the product shows it.

### M2-03 Run on a copy, then live (Leo)
1. Start the pipeline on a copy as in M1-21. Record the test run id.
2. Run live: the production run, using the live control on the screen (or POST `/api/v1/build/p/{pid}/run` with the body the screen sends for live; record it). Record the production run id from GET `/api/v1/ops/runs?mode=production`.

### M2-04 Limits check and the duplicate question (Leo)
1. API proof run: POST `/api/v1/recon/limits/run` with `{"as_of_date": "2026-08-31", "cutoff": "2026-09-02T06:00:00Z"}`. Save to `D:/Temp/uc5/aug_limits_api.json`.
2. Real-person run: Action > Reconciliations, **Check as at** `2026-08-31`, **Run now**. Compare.
3. Expected (key, August):

| Line | Figure | Max | Headroom | Result | Cause |
|---|---|---|---|---|---|
| Harborview | 5.71% (2,259,200 of 39,552,000) | 6.00% | 0.29 | inside | - |
| Listed equity | 80.06% (31,665,800) | 90.00% | 9.94 | inside | - |
| Cedarpoint C plus D | 57.38% (12,925,000 of 22,525,000) | 55.00% | -2.38 | breach, over by 536,250 | stale data (Fund D 153 days old) |
| Hedge funds | 54.56% (12,300,000 of 22,545,000) | 60.00% | 5.44 | inside | - |
| Question: Pacific Rim | 1,051,000 = 2.66% | - | - | question | - |

4. Early warning: none expected (C11). Record "not shown".
5. Duplicate check (C10): the key expects a note, not a second case. The product titles cases with the as-at date, so expect a **new** August case for Cedarpoint. Record the July case status (open or closed), the number of Cedarpoint cases, and their titles. A second case for the same standing breach is a **note**: "a new case each month for the same stale breach".

### M2-05 Action (Sofia, Mei)
1. Sofia reviews the August case and records the same decision as in July: stale, not real (take, note, resolve as in M1-28).
2. Mei: the Fund D 30 Jun statement is still missing. She adds a note on the statement item. No message is sent.
3. Record whether the product asks for a decision each month, and the case status after the decision.
4. Admin NAV difference (planted issue 11, Fund C): Mei opens the Fund C statement item and reads 8,420,000 (administrator) and 8,275,000 (amended). Record whether the product explains the 145,000 difference or leaves the reader to find it.

### M2-06 Consume (Daniel)
1. Open the August dashboard (GET `/api/v1/consume/dashboards/{did}/view`). Check the figures against the M2-04 table. Check the stale flag shows on Cedarpoint. Screenshot `uc5-14-aug-limits-run` (from M2-04) and the dashboard as needed.

---

## 8. Month 3 (September 2026): limit v2, two breaches, one stale

Sources: `docs/demo/uc5/sources/2026-09/administrator_positions_2026-09-30.xlsx` and `docs/demo/uc5/sources/2026-09/limits_signed_v2_2026-08-28.xlsx`. Received 2 Oct 2026 06:00 UTC. Limit v2 was signed 28 Aug 2026 and takes effect 1 Sep 2026: the single-name cap for Harborview moves from 6.00% to 5.00%. Other lines are unchanged.

### M3-01 Limit v2 (Leo proposes, Daniel signs)
1. Profile and load the v2 workbook (as in M1-14 and M1-17). Its Version cell reads v2.
2. Leo proposes the v2 cap effective 1 Sep 2026: POST `/api/v1/rules/limit_single_name_liquid` with
   ```json
   {
     "definition_text": "EG-LIQUID: Harborview Semiconductor must be between 0% and 5% of the portfolio. Signed v2 (Daniel Foo, 28 Aug 2026), effective 1 Sep 2026. Other rules unchanged.",
     "parameters": {"dimension": "single_name", "bucket": "Harborview Semiconductor", "min_pct": 0.0, "max_pct": 5.0, "portfolio_code": "EG-LIQUID"},
     "effective_from": "2026-09-01",
     "rule_type": "limit"
   }
   ```
3. Daniel approves: POST `/api/v1/rules/versions/{vid}/approve`.
4. GET `/api/v1/rules/limit_single_name_liquid/history`. Expected: the 6.00% version effective 1 Jan (M1-19), the 5.00% register version effective 1 Jan 2026 from the seed, and the 5.00% v2 effective 1 Sep 2026. The product uses the newest version effective on the date. Record the versions listed, and the one in force on 30 Sep (the September run carries the rule version id).
5. Record how the register handles a second 5.00% version. If it refuses, record the refusal text. A refusal here is a finding about the register, not a failure of the answer key.

### M3-02 Run and check (Leo)
1. Start the pipeline on a copy, then live (as M2-03). Record both run ids.
2. API proof run: POST `/api/v1/recon/limits/run` with `{"as_of_date": "2026-09-30", "cutoff": "2026-10-02T06:00:00Z"}`. Save to `D:/Temp/uc5/sep_limits_api.json`.
3. Real-person run: Action > Reconciliations, **Check as at** `2026-09-30`, **Run now**. Compare.
4. Expected (key, September):

| Line | Figure | Max | Headroom | Result | Cause |
|---|---|---|---|---|---|
| Harborview Semiconductor (EG-LIQUID) | 5.75% (2,368,000 of 41,200,000) | **5.00%** | -0.75 | **breach, over by 308,000** | **real breach** (inputs recent and verified) |
| Listed equity | 80.61% (33,210,500) | 90.00% | 9.39 | inside | - |
| Cedarpoint C plus D (EG-B-OPS) | 56.50% (12,925,000 of 22,875,000) | 55.00% | -1.50 | **breach, over by 343,750** | **stale data**: Fund C valued 30 Jun (92 days); Fund D valued 31 Mar (**183 days**, not 192: C14); Fund E 9,950,000 not yet verified |
| Hedge funds | 54.95% (12,500,000 of 22,750,000) | 60.00% | 5.05 | inside | - |
| Question: Pacific Rim | 1,122,000 = 2.72% | - | - | question | - |

5. Expected cases: two new limit cases dated 30 Sep 2026: Harborview (cause real breach) and Cedarpoint (cause stale data). The separate causes are the point of this month. Record each cause as shown.
6. Harborview's maximum on this run must be 5.00% (the v2 version). A 6.00% maximum is a **wrong number**. Record the rule version id the run used.
7. The Cedarpoint "why" text names the stale inputs (Fund D, Fund E) and their days. Record the day count shown (183 expected; 192 is the seed-text error, C14).

### M3-03 Action: Harborview real, Cedarpoint stale (Sofia, Raj, Mei)
1. Sofia opens the Harborview case (Action, Cases). She takes it (subject to G3). She notes: "Real breach. Cure by trim." Record.
2. Sofia asks finance: POST `/api/v1/cases/{cid}/ask_finance` with `{"to": "Raj Patel"}` (or the screen's ask-finance control). Record the response.
3. Raj approves the trim: Raj signs in and opens the case. POST `/api/v1/cases/{cid}/approve` with `{"rationale": "Trim Harborview Semiconductor to 5.00% or below. No trade is placed in this product."}`. Record whether Raj can act (approver) and where the approval lands (the case, or an approval screen).
4. No trade is placed in the product. Record the case status after the decision. Expected: the case stays open until the trim is booked by the administrator (October, M4-02).
5. Sofia opens the Cedarpoint case and decides **stale, not real**. She notes that the statements are requested: Fund C 30 Sep, Fund D 30 Jun, Fund E verification (contact in the key: Hana Sato). Mei records the chase. The case may stay open until the statements arrive, or be resolved with code `stale_data`. Record which the product allows.
6. Planted issue 5 check: the Cedarpoint case must not show as a real breach. Record the cause shown on the case list.

### M3-04 Consume (Daniel)
1. Open the September dashboard. Check two breaches: one real (Harborview, -0.75 points) and one stale (Cedarpoint, -1.50 points). Record the tile values and causes. Screenshot `uc5-15-sep-harborview-case` and `uc5-16-sep-cedarpoint-case` at M3-03.

---

## 9. Month 4 (October 2026): resolved breach, new real breach, open UC8 carry-over

Sources: `docs/demo/uc5/sources/2026-10/administrator_positions_2026-10-31.xlsx` and `docs/demo/uc5/sources/2026-10/limits_signed_v2_2026-08-28.xlsx`. Received 3 Nov 2026 06:00 UTC. The limit version is unchanged (v2).

**Date warning:** the seed clock is pinned to 9 Oct 2026 (`demo_today`, `tools/seed_10uc.py`). A run as at 31 Oct is after that pinned date. Record any warning the product shows and whether the run is accepted.

### M4-01 Receive and load (Leo)
1. Upload and load both files as in M2-01. Record the check lines. Key figures: EG-LIQUID 42,392,020.00; latest known EG-B-OPS 24,100,000; latest known EG-FUNDS 22,900,000. The footer basis may differ (G4).

### M4-02 Benchmark against September (Leo)
1. Save the September limits result as text (`D:/Temp/uc5/sep_limits_report.txt`, from `sep_limits_api.json`) and give it as the benchmark, as in M2-02.
2. Check the variance line by line:
   - Harborview: 5.75% to 4.28%. The move is the 6 Oct sale of 5,000 shares (T-20261006-005), booked at the administrator. Record whether the variance names the trade or only the number.
   - Cedarpoint: 56.50% to 58.71%. The move comes from revised valuations: Fund C 8,900,000; Fund D 30 Sep statement 5,250,000; Fund E confirmed 9,950,000. Record whether the variance shows the reason.
   - Hedge funds: 54.95% to 54.80%.
3. Planted issue 9 (estimates): H1 and H2 are manager estimates in October. The product has no estimate flag (C12). Record "not flagged" as **missing**.
4. Planted issue 10 (UC8 carry-over): the administrator holds Northwind Logistics at 60,200 (its 10,200 buy); the trading export says 12,000; the 1,800-share difference is open (75,870 at 42.15). Record whether the limits run mentions it (it must not change a limit figure) and whether the UC8 break shows in Action.
5. Planted issue 12 (scope): the positions file covers the limit-monitored portfolios only (EG-GROWTH funds A and B are not in it). Record the denominator the product uses. A file total shown as office NAV is a **wrong number**.

### M4-03 Run and check (Leo)
1. Start on a copy, then live (as M2-03).
2. API proof run: POST `/api/v1/recon/limits/run` with `{"as_of_date": "2026-10-31", "cutoff": "2026-11-03T06:00:00Z"}`. Save to `D:/Temp/uc5/oct_limits_api.json`.
3. Real-person run: Action > Reconciliations, **Check as at** `2026-10-31`, **Run now**. Compare.
4. Expected (key, October):

| Line | Figure | Max | Headroom | Result | Cause |
|---|---|---|---|---|---|
| Harborview | 4.28% (1,815,000 of 42,392,020) | 5.00% | 0.72 | inside (the September breach is cured; the product does not close its case) | - |
| Listed equity | 78.76% (33,386,520) | 90.00% | 11.24 | inside | - |
| Cedarpoint C plus D (EG-B-OPS) | 58.71% (14,150,000 of 24,100,000) | 55.00% | -3.71 | **breach, over by 895,000** | **real breach** (all inputs 30 Sep or later) |
| Hedge funds | 54.80% (12,550,000 of 22,900,000) | 60.00% | 5.20 | inside (estimates, not flagged: M4-02 step 3) | - |
| Question: Pacific Rim | 1,143,000 = 2.70% | - | - | question | - |

5. Expected cases: one new real-breach case for Cedarpoint dated 31 Oct. The September Cedarpoint stale case stays open or resolved, with no duplicate for the same date. The September Harborview case is not re-opened; it stays as September's case until someone closes it. Record this.

### M4-04 Action (Sofia decides; Raj approves; Mei chases; Pacific Rim decision left open)
1. Sofia takes the new Cedarpoint case and notes "Real breach, from revised statements." Cure: a trim or a redemption request, decided with Raj. No trade is placed in the product. Record.
2. Sofia closes the September Harborview case with code `cured` and the note "Cured at 6 Oct sale; 4.28% at 31 Oct." (POST `/api/v1/cases/{cid}/resolve`). Record whether the product closed it by itself (it should not) and the status after.
3. Mei chases Fund E if it is still unverified and notes it. No message is sent.
4. Planted issue 8 (Pacific Rim, no asset class in four months): the item must still be in questions. A real person asks the rule owner before setting a class. Record "Needs a class" shown. Do not set the class in this test; record that the decision belongs to Daniel and Anita.

### M4-05 Consume and delivery (Daniel)
1. Open the October dashboard. Check: Harborview 4.28% inside; Cedarpoint 58.71% real breach; hedge funds 54.80%; Pacific Rim question count 1. Record each tile. Screenshot `uc5-19-oct-dashboard`.
2. Open the delivery channel preview (M1-27). Check the October figures show as percentages. Do not send.

### M4 end check (Daniel, Anita, Grace)
- Run history: GET `/api/v1/recon/runs` and GET `/api/v1/ops/runs`: four production runs (July to October), each with a run id and as-at date. Record the case count per run.
- Action: open, closed and resolved cases for all four months, each with its reason. Record any case that is open with no owner.
- Consume: each month's dashboard is readable.
- Access check (Grace): each person, one at a time, tries the step they need. Any 403 on a step a person needs is a finding. Record the message.

---

## 10. Expected results summary (from the answer key, with the tolerances in C13)

| Month | Harborview (max) | Cedarpoint (max 55%) | Hedge funds (max 60%) | New cases | Result |
|---|---|---|---|---|---|
| Jul | 5.73% (6.00%) inside, headroom 0.27 | 57.38%, breach over 536,250, stale | 54.49% inside | 1 (Cedarpoint, stale) | stale breach, not all inside |
| Aug | 5.71% (6.00%) inside, headroom 0.29 | 57.38%, breach over 536,250, stale | 54.56% inside | 1 new by title date (C10) | no early warning (C11) |
| Sep | 5.75% (5.00%) breach over 308,000, **real** | 56.50%, breach over 343,750, **stale** | 54.95% inside | 2 (Harborview real, Cedarpoint stale) | two causes, one real |
| Oct | 4.28% (5.00%) inside, headroom 0.72 | 58.71%, breach over 895,000, **real** | 54.80% inside (estimates) | 1 new (Cedarpoint real) | Harborview cured; Cedarpoint real |

Pacific Rim Convertible 2029 is a **question** every month (1,084,000 / 1,051,000 / 1,122,000 / 1,143,000), in no bucket, with no case.

---

## 11. Milestone screenshots (save to `D:/Temp/uc5/shots/`)

| File | Screen | Step |
|---|---|---|
| `uc5-01-mode` | sign-in header with "Testing models (free tier)" | M1-01 |
| `uc5-02-starting-rules` | Settings > Rules (starting register) | M1-03 |
| `uc5-03-starting-cases` | Action > Cases (seeded cases) | M1-03 |
| `uc5-04-north-summary` | North closing summary | M1-05 |
| `uc5-05-signed-intent` | intent after signing | M1-06 |
| `uc5-06-architecture-summary` | architecture summary with sources from the intent | M1-08 |
| `uc5-07-pack-approved` | design pack, approved | M1-11 |
| `uc5-08-intake-uploaded` | intake list with the two July files | M1-13 |
| `uc5-09-approval-panel` | approval panel "What Lumen checked" | M1-26 |
| `uc5-10-jul-limits-run` | Action > Reconciliations, limits card after the July run | M1-22 |
| `uc5-11-jul-case` | Action > Cases, the July Cedarpoint case | M1-28 |
| `uc5-12-operations-runs` | Operations > Runs with test and production run ids | M1-24 |
| `uc5-13-dashboard-consume` | Consume dashboard, July | M1-29 |
| `uc5-14-aug-limits-run` | August limits card | M2-04 |
| `uc5-15-sep-harborview-case` | September Harborview case (real) | M3-03 |
| `uc5-16-sep-cedarpoint-case` | September Cedarpoint case (stale) | M3-03 |
| `uc5-17-oct-limits-run` | October limits card | M4-03 |
| `uc5-18-oct-cedarpoint-case` | October Cedarpoint case (real) | M4-04 |
| `uc5-19-oct-dashboard` | October Consume dashboard | M4-05 |

Full-page shots only where the step asks for them.

---

## 12. Issues to log (severity and what each means)

Severity: **blocker** (the step cannot finish); **wrong number** (outside tolerance without a stated reason); **missing** (a required screen or flag does not exist); **unclear** (a real person would not know what to do); **note**.

Planted issues from the answer key. Each gets a line in `docs/test/uc-live/UC5-ISSUES.md` when it appears, or when it fails to appear:

1. Limit version conflict (5.00% register and universe vs 6.00% v1). Decision G1. Log the register and the version each run used.
2. July is not clean: Cedarpoint stale breach. Log the cause shown.
3. No August early warning. Log: no early-warning feature exists (C11), so "not shown" is expected; record it as **missing**.
4. September Harborview is a real breach. Log the case, cause, owner and the trim approval (Raj).
5. September Cedarpoint is a stale breach. Log the cause shown: stale, not real.
6. October Harborview is cured by the 6 Oct sale. Log how the case closes (it does not close by itself).
7. October Cedarpoint is a real breach from revised valuations. Log whether the variance names the reason.
8. Pacific Rim Convertible 2029 has no asset class. Log "Needs a class" every month, in no bucket.
9. October hedge fund estimates. Log whether flagged. Expected not flagged (C12): **missing**.
10. UC8 carry-over: Northwind Logistics 1,800-share difference. Log whether it appears in Action and whether it touches a limit figure.
11. Fund C NAV difference in July (8,420,000 administrator vs 8,275,000 amended). Log whether explained.
12. Scope: EG-GROWTH funds are not in the positions file. Log the denominator the product uses.

Findings from this plan (log them even if the key does not name them):

- F1: the seeded register holds 5.00% from 1 Jan 2026 (C1).
- F2: the seed already holds limit cases dated 9 Oct 2026 (C2).
- F3: a participant cannot act on a case (C3).
- F4: control totals on the positions footer are administrator totals (C5, G4).
- F5: a load needs an approved mapping; the first load writes nothing (C7).
- F6: the recon screen cannot set a cutoff (C8, G6).
- F7: a limits run has no test or production mark (C9).
- F8: a new case each month for the same standing breach (C10).
- F9: no early-warning feature (C11).
- F10: no estimate flag (C12).
- F11: Fund D's age in the seed text is 192 days; the key and the date arithmetic give 183 (C14).
- F12: walkthrough findings re-tested here: a starter tile missing for a named figure; a duplicate tile; fractions in the email preview; the approval panel says "no reviewed run" after a pass; the approved dashboard not in Consume.

---

## 13. Stop rules

- Stop and report if a step returns 500, a raw error or a stack trace on screen. Keep the text.
- Stop and report if a figure is outside tolerance (share 0.01 point; over-by USD 500) without a stated reason in the product.
- Stop and report if a person can act on a case they have no role for, or cannot act on one they do.
- Stop and report if a run writes to production when it was meant as a test run (the badge or `GET /api/v1/ops/runs?mode=test` shows the wrong mode).
- Stop and report if the mode line says Real-use models.
- Do not fix product code. Do not edit `data/`. Do not decide a gate for the person who owns it.

---

## 14. Deliverables

- `docs/test/uc-live/UC5-RUN-LOG.md`: one row per step (section 4), with run ids, figures and screenshot names.
- `docs/test/uc-live/UC5-ISSUES.md`: each issue or finding (section 12), with severity, step id, expected vs actual, and the first line of `.sh-tmp/testenv/uc5/server.log` for any error.
- Screenshots in `D:/Temp/uc5/shots/`. JSON responses in `D:/Temp/uc5/`.
- A short honest opinion at the end of the run: what a risk owner could use each month, what she could not, and what must change before a monthly run is trusted.

---

## 15. Review: what is missing, and what to build next (honest)

These are gaps found while writing the plan. They are product gaps, not test steps. Each is a recommendation; none is built.

1. **Rules from the signed workbook.** The limits file is not read as a rule source. Every change is retyped by hand (M1-19, M3-01). A typo there changes a breach. Recommend: import the signed sheet as a proposed rule version, with a diff against the register, for Daniel to sign.
2. **Conflicting signed versions shown as a decision.** The register and the signed file disagree for January to August, and nothing in the product asks which is signed (G1). Recommend: a blocking item in Action for the CIO.
3. **Early-warning line.** The product has no line for "inside but within X points". The story needs it for the risk owner. Recommend: a band set per signed rule (signed, not a generator constant).
4. **Estimate flag.** Limit figures that use manager estimates are not marked (M4-02). Under the signed estimate rule this is a must-have. Recommend: mark each limit line that uses an estimate, and show it on the case.
5. **Case noise.** A standing breach opens a new case each month (C10). Recommend: one case per breach that stays open, with a dated history of each month's figure.
6. **No test or production mark on limit runs** (C9). A monthly limit result needs the same test and live split as the pipeline.
7. **No cutoff on the screen** (C8, G6). A real person cannot reproduce a past month's receipt time from the screen. Recommend: a cutoff field under **Check as at**, defaulting to the file receipt time.
8. **Risk owner cannot act** (C3). A participant who must decide a breach is blocked. Recommend: the risk-owner role is an explicit assignment on the rule itself, so the decision maker is named on the rule, not only on the account.
9. **Control totals on mixed bases** (C5). The footer is the administrator basis and the limit uses latest-known values. Recommend: show both on the check, with the difference named.
10. **Approved dashboard in Consume.** If it still does not appear, the monthly reader (Daniel) cannot see the result without asking. This is the most important fix for monthly use.
11. **Breach to trade.** The product records a decision to trim but cannot link it to the trade in the trading export or to the administrator's booking (M3-03, M4-02). Recommend: a link from the case to the booked trade id, so the cure is checked, not asserted.
12. **Delivery figures.** Email previews printed raw fractions in the walkthrough (M1-27). Recheck; it is a visible error for the CIO.

What is in good shape, from reading the code: the limit arithmetic is clear; the stale rule (90 days or unverified) is applied and named; the causes are split (real and stale); holdings with no asset class are kept out of every bucket; and each case carries its over-by amount.
