# UC6 live test plan: can we meet the capital calls?

Scope: private-asset capital calls, distributions and commitments for Evergreen Office (a fictional family office). Entities EG-HOLD, EG-TRUST and EG-B. Funds A to E (managers: Northgate, Cedarpoint, Saltmarsh). Four monthly cycles: July, August, September and October 2026. October is as at 9 Oct 2026 (cash to 8 Oct). Synthetic data only. Use no other company, prospect or client name.

Expected results come from `docs/demo/uc6/ANSWER-KEY.md` (section numbers below refer to it). Where the product does something different, the step says **[risk]** and the tester records what the screen or API actually returns. A prediction is never a pass.

Status: plan only. Nothing in `sh_platform/` or `ui/src/` was changed. No commit, no push. Nothing written to the repo `data/` folder. Ports 8400, 8504 and 8200 are not used. This plan replaces the earlier draft of this file, which was written before the product's capital-call code (`k4`, `k6`, `e2`) was read.

---

## 0. Ground rules for the tester

- Work as a real person does: sign in as each role, use the screens, upload the files, press the buttons. Use the same HTTP route the screen calls only where the screen has no control for the step. Record which one you used.
- Never type a password into chat, a file in the repo, or a run log. Read it from the credentials file in your own editor and type it into the sign-in form.
- Keep the mode on **Testing**. Never switch to **Real use**.
- Temporary files go to `D:/Temp/uc6/`. Test output goes to `.sh-tmp/testenv/uc6/` (gitignored). Use absolute paths.
- Do not edit product code. When something is wrong, record it in the issues log (section 9) and continue with the next step as the role that can do it.
- Every run gets a run ID from the product. Record it. No run ID, no pass.

---

## 1. What the product does for UC6 (read from the code, 12 Oct 2026)

Two capital-call paths exist. The plan tests both and records which one the figures come from.

**Path K (already built, use case UC6 in its own header).** `sh_platform/v1/k6_liquidity.py`, read by `k4_office.py` and the Office view.
- Commitments and cash calls are append-only rows. A change is a new row that supersedes the old one.
- A notice is recorded as `noticed` when its PDF is read (`e2_extract._noticed`), and as `confirmed` when a person confirms the field (`e2_extract._confirm_notice`). The confirmed row supersedes the noticed row.
- A **confirmed** call due within the signed rule `cash_call_alert_days` (default 30) opens a Finance case "Fund the capital call" (`k6_liquidity.alert_if_due`). A noticed-but-not-confirmed call does not.
- `forecast()` gives, per entity: available cash, calls and distributions due in 30, 60 and 90 days, cash after those calls, uncalled commitment, and the calls not confirmed yet.
- Cash comes from `position_snapshots` for cash instruments. The administrator view is preferred over the trading export (`k6_liquidity._cash`).
- Screen: Consume, Office view (`/centre/consume/office`). API: `GET /api/v1/office/liquidity?currency=USD&as_of=YYYY-MM-DD` (`k4_routes.py`, role list in `k4.permissions.yaml`). The route passes `as_of` only; `cutoff` is not exposed.

**Path P (the build flow in the brief).** Intent with North, design pack by Span, builder runs on a copy, benchmark, go live, Lumen starter, approvals (`docs/plan/BUILD-FLOW-V6.md`, `V6-architect.md`, `V6-builder.md`, `V6-lumen-starter.md`).
- The builder connects the sources the approved pack names, runs on a copy, compares figures with a benchmark and goes live on the pack's schedule.
- Span's chat tools draft **gold tables only**. A new silver table (for example a capital-call schedule) needs a model change proposed by a data engineer, approved by the head of data (`docs/plan/v6-landings/DM1-data-model-view.md`; routes `POST /api/v1/model/proposals`, `POST /api/v1/model/proposals/{n}/approve`, or `POST /api/v1/build/p/{pid}/plan/propose` with `model_change`).

**What this means for the test.** Path K already holds the commitments, the notices and the liquidity forecast. Path P would hold them a second time. The test must show which path produces each figure on the screen, and whether the two agree. This is the first decision for Nitin (section 0.3, decision D1).

**Other facts used by the steps**
- Intake (files): `/centre/data/intake?project=<pid>`, control "Upload a file", accepts `.xlsx`, `.xlsm`, `.csv` only. Route `POST /api/v1/intake/upload` (multipart: `data`, `filename`, `source_code`, `sensitivity`), then `POST /api/v1/intake/files/{id}/profile`, then `POST /api/v1/intake/files/{id}/load` (button "Load this file", after the file is approved in the mapping).
- Evidence (PDFs): route `POST /api/v1/evidence/documents` (upload), `POST /api/v1/evidence/documents/{doc_id}/extract`, `GET .../documents/{doc_id}/fields`, `POST /api/v1/evidence/fields/{field_id}/confirm|correct|reject` (`e2a_routes.py`, `e2b_routes.py`). The intake does not take PDFs. The upload control on the Evidence list page is at `/centre/evidence` [verify the path and label on screen].
- Pipeline runs: `POST /api/v1/build/p/{pid}/run?mode=sandbox|live` (sandbox is the "copy" run, live is production). Runs list `GET /api/v1/build/p/{pid}/runs`. Schedule `PUT /api/v1/build/p/{pid}/schedule`.
- Run IDs (RUN1): `GET /api/v1/ops/runs?mode=test|production&kind=`, `GET /api/v1/ops/runs/{run_id}` (with steps), `GET /api/v1/ops/pipelines`. Screen: Operations (`/centre/operations`), section "Runs".
- Schedule trigger: a pack schedule with `freq = on_arrival` runs when a file from one of its sources loads (`b6_schedule.on_arrival`). Any other schedule runs at its time on the server clock. A monthly schedule does not run when files are dropped.
- Action: `/centre/action`; API `GET /api/v1/action/landing`. Case routes under `/api/v1/cases` (`e4a_routes.py`): `GET /api/v1/cases`, `POST /api/v1/cases/{cid}/take`, `/assign`, `/submit`, `/approve`, `/send_back`, `/resolve`, `/dismiss`, `/ask_finance`, `/note`. Reconciliation "Close as timing" is `dismiss`.
- Starter dashboard: `POST /api/v1/build/p/{pid}/studio/starter`; `POST .../studio/{did}/starter/accept`, `/submit`, `/approve`, `/send-back` (`b7_routes.py`).
- Consume: `/centre/consume/office`; per-project Consume API `/api/v1/consume/p/{pid}/...` (`cx_routes.py`).
- Modes: header switch and **Settings > Testing or Real use** (`/centre/settings/mode`). The line under the agent reads "Testing models (free tier)" in Testing mode, "Real-use models" in Real use (`ui/src/v1/router`).

**Known facts that change the test**
1. The seed pins the company clock to **9 Oct 2026** (`wh.set_demo_today`, from `tools/seed_10uc.py`). No screen or route sets it. Only `/api/v1/office/liquidity?as_of=` can ask for an earlier date. The pipeline and the builder run on the clock, not on a cycle date.
2. The seed is not empty. `docs/test/10uc_universe.json` already holds the UC6 October facts, including the Finance case text "Fund the capital call". See gate G1.
3. The sources have no prior liquidity report. The answer key gives the figures, so the benchmark for August to October must be built from them (section 0.4, decision D4).

---

## 2. Gate: decide before the first run (blocking)

**G1. Seeded UC6 facts.** The universe (`docs/test/10uc_universe.json`, rows P21 to P24) already has: Entity B available 880,400; after both calls -169,600; a Finance case for the Cedarpoint Ventures III call; Cedarpoint Opportunities II 250,000 on 4 Dec; Northgate 320,000 expected 16 Nov; commitments called 31,250,000 on 9 Oct (universe P24; July to September is 30,550,000). A fresh seed therefore shows the October answer before any file is loaded. A pass on a figure would prove nothing.

Steps:
- G1.1 Start the server (section 3). Sign in as Leo Park and as Mei Chen. Open `/centre/action` and `/centre/consume/office`. Search the page text (Ctrl+F) for: `Fund the capital call`, `880,400`, `430,400`, `-169,600`, `Cedarpoint Ventures III`, `Saltmarsh`, `Northgate`. Record each hit with its screen file (`.sh-tmp/testenv/uc6/shots/G1-*.png`).
- G1.2 Record the starting state with `GET /api/v1/cases`, `GET /api/v1/ops/runs`, `GET /api/v1/office/liquidity?currency=USD` (no `as_of`) and `GET /api/v1/build/projects`. Save each response to `.sh-tmp/testenv/uc6/api/G1-*.json`.
- G1.3 Choose one option (decision D0) and write it on the first line of the run log:
  - **Option A (recommended).** A UC6-only seed: the seed without the universe's UC6 rows (P21 to P24 and the UC6 cash and commitment rows). Needs a seed change that is not in this plan. Clean test.
  - **Option B.** Keep the demo seed and treat seeded UC6 figures as noise. A figure passes only if the files the tester loads produce it too. Record each such pass as "figure also present in seed".
  - **Option C.** Stop UC6 until Option A exists.
- G1.4 Do not go past this gate until Nitin has chosen. If G1.1 shows October answers and no option is chosen, record it as blocking and stop.

**D1 (decide before Month 1): which path produces the calls?**
- D1-K: use Path K (notices read and confirmed in Evidence, liquidity from `k6_liquidity`). Span does not add a silver schedule.
- D1-P: use Path P (Span drafts a silver `capital_call_schedule` as a model change; the builder loads it).
- D1-both: run both and compare. This is the default for this test, because the brief asks for D1-P and the product already has D1-K. Record the difference in section 8.

**D2 (decide before Month 2): as-of date.** Options: (a) leave the company clock at 9 Oct and use `as_of=` on the liquidity route for Jul, Aug and Sep (default for this test); (b) add a company as-of setting (a product change, not in this plan).

**D3 (decide before Month 4): October cut-off.** Keep 9 Oct (cash to 8 Oct, as in the answer key and the universe), or run a separate 31 Oct cycle. The answer key (section 5, deviation 1) recommends 9 Oct.

**D4 (decide before Month 2): the benchmark.** The brief says "check against last month's liquidity report". No such report is in the sources. Default for this test: the tester writes a one-page text file `D:/Temp/uc6/benchmark_liquidity_<YYYY-MM>.txt` with one line per figure, label then number, using the answer-key figures for the previous month (section 6). The file is a constructed benchmark and is recorded as one. It is never placed in `docs/demo/uc6/sources/`.

---

## 3. Start the tester's own server on port 8811

Run in Git Bash. Start the server as a background shell command, never inside an agent.

3.1 Clean the environment (simple mode: neither `DATABASE_URL` nor `REDIS_URL` may be set).

```sh
unset DATABASE_URL REDIS_URL
export TMP=/d/Temp TEMP=/d/Temp TMPDIR=/d/Temp
cd "/d/Projects/01-Project Signal Harbor/Repo 1.0"
mkdir -p /d/Temp/uc6 .sh-tmp/testenv/uc6/shots .sh-tmp/testenv/uc6/api
```

3.2 Check that port 8811 is free. In PowerShell: `netstat -ano | findstr :8811` must print nothing. If it prints a line, stop and record it.

3.3 Seed the data root (idempotent; creates `_control/seed_credentials.txt`). Do not print that file in the terminal.

```sh
python tools/seed_demo_boot.py --data-root "/d/Projects/01-Project Signal Harbor/Repo 1.0/.sh-tmp/testenv/uc6/data"
```

Record the `demo-ready` lines. This can take several minutes; run it as a background command and wait for it to finish. For a clean root under Option A, use `--reset` only on this data root (it refuses the repo `data/`).

3.4 Start the server with the scheduler off and its own data root (`tools/serve_test.py`). Run in the background.

```sh
python tools/serve_test.py --port 8811 --data-root "/d/Projects/01-Project Signal Harbor/Repo 1.0/.sh-tmp/testenv/uc6/data"
```

The log goes to `.sh-tmp/testenv/uc6/server.log`. Check it: `grep -i error .sh-tmp/testenv/uc6/server.log` (a failed model call is a warning, not a stop).

3.5 Health check. Open `http://127.0.0.1:8811/login`. Sign in as Daniel Foo (section 4). The line under the agent must read **Testing models (free tier)**. If it reads "Real-use models", switch to Testing in Settings > Testing or Real use before going on.

3.6 At the end, stop only the server process on 8811 (`netstat -ano | findstr :8811`, then stop that PID).

Record: seed output, server start line, the mode line text, the server PID.

---

## 4. Sign-ins and roles

Addresses follow the pattern `<first>.<last>.evergreen@example.test`. Passwords are in `.sh-tmp/testenv/uc6/data/_control/seed_credentials.txt` (or the shared password if `SH_DEMO_PASSWORD` was set).

| Person | Address | Role to expect | What UC6 uses them for |
|---|---|---|---|
| Daniel Foo | daniel.foo.evergreen@example.test | sponsor | Signs the intent; approves the starter dashboard |
| Mei Chen | mei.chen.evergreen@example.test | owner (business owner) | Writes the intent with North; submits the starter; matches and confirms calls; acts on Action |
| Raj Patel | raj.patel.evergreen@example.test | approver | Approves the funding decision and the 30-day view; closes timing cases |
| Anita Rao | anita.rao.evergreen@example.test | analyst + head_of_data | Approves the design pack, the plan and the model change |
| Leo Park | leo.park.evergreen@example.test | analyst (data engineer and ops) | Architecture, samples, uploads, runs, builder, go live |
| Sofia Reyes | sofia.reyes.evergreen@example.test | participant (risk owner) | Reads the amendment and the unconfirmed call |
| Grace Ong | grace.ong.evergreen@example.test | company_admin | Checks access only |

Check each person's role on arrival: open **Settings** and count the items (expected per ROLE1: Mei 3, Daniel 3, Sofia 3, Raj 4, Anita 7, Leo 8, Grace 16). The seed credentials file lists Mei as `analyst` [risk R0]: if her Settings shows 8 items, record it as a role issue (ROLE1 says owner).

Sign in: `http://127.0.0.1:8811/login`, type the address in `#email`, the password in `#password`, press Enter. The session cookie is `sh_csrf`; for API calls send its value as the `X-CSRF-Token` header.

API helper (optional; save as `D:/Temp/uc6/uc6_api.py`, run with `python -I`). It signs in through the page as the lib pattern does and sends calls as that person:

```python
import json, sys
from playwright.sync_api import sync_playwright
BASE = "http://127.0.0.1:8811"

def session(email: str, password: str):
    pw = sync_playwright().start()
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.goto(BASE + "/login")
    pg.fill("#email", email)
    pg.fill("#password", password)
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(2500)
    return pw, b, ctx

def call(ctx, method: str, path: str, body=None):
    token = next((c["value"] for c in ctx.cookies() if c["name"] == "sh_csrf"), "")
    r = ctx.request.fetch(BASE + path, method=method,
                          data=None if body is None else json.dumps(body),
                          headers={"content-type": "application/json", "X-CSRF-Token": token},
                          timeout=240000)
    try:
        return r.status, r.json()
    except Exception:
        return r.status, r.text()[:300]
```

Passwords come from the credentials file by reading it in the script, never printed. Uploads of files go through the UI control where one exists (section 5 and 6); the helper is for reading state and for calls with no screen.

---

## 5. Month 1 (July 2026): the full build

Each step: who, what to do (exact click path or route), the expected result (answer key), and what to record. The run log line format is in section 8. Screenshot names are in section 7.

**Before M1.1.** Confirm gate G1 and D1, D4 (section 2). Record the project list `GET /api/v1/build/projects` (should be empty of UC6 under Option A).

**M1.1 Build landing (Mei).** Sign in as Mei. Click **Build** in the top menu, or open `/centre/build`. Expected: the four steps (Intent with North, Architecture with Span, Pipelines with Span, Dashboards and delivery with Lumen). Record the landing text.

**M1.2 Intent with North (Mei, by chat).** On the landing, press **New project**. North asks what is needed. Type the messages below one at a time (paste the text from this list; do not add the answer key). After each reply, record what North asked and whether it asked one question or a form.

Messages to type, in order:
1. `I need a monthly view of whether Evergreen Office can meet the capital calls on its private funds. Readers: me, Raj Patel and Sofia Reyes. Decision: whether to fund a call from Entity B, and when.`
2. `The figures: available cash by entity (Evergreen Holdings EG-HOLD, Evergreen Family Trust EG-TRUST, Entity B EG-B), calls due in the next 30 days, calls due in 31 to 60 days, cash after those calls, uncalled commitment by fund, and any call not yet confirmed.`
3. `Cash is the administrator's closing cash on the last cash day of the month. The bank statements are a timing check, not the figure. Entity B for October is 880,400.00 on 8 October.`
4. `A call is due when its due date falls within 30 days of the as-at date. A notice is noticed until the office confirms it; only confirmed calls count as called. A manager's call plan in the commitments file is an estimate and is never due.`
5. `A distribution is money coming in, never a call. An amended notice replaces the earlier amount with the same reference; count it once.`
6. `Sources: (1) the commitments schedule, an Excel workbook sent at month end; (2) the bank cash files, one CSV per entity, daily, sent each month; (3) the administrator's cash report, a CSV, the official figure; (4) the capital call and distribution notices, PDFs from the managers; (5) the notice receipt log, a CSV that says when each notice reached us.`
7. `The bank files and the administrator report arrive as CSV each month by upload. The commitments schedule arrives as Excel by upload. The notices arrive as PDF, one per notice, uploaded by hand.`
8. `Readers see the view each month on the fifth business day. Raj approves the 30-day view.`
9. `That is everything. Please draft the intent and the process map.`

Expected (answer key sections 1 and 2): North drafts the intent and the process map as they talk, asks at most one question per turn, and does not ask for a form. North's definitions match messages 2 to 5. **[risk R1]** North may write a sign or unit wrongly (the UC4 walkthrough found "portfolio return minus benchmark" written without the points unit); check the figure definitions on the sign page in M1.4.

Record: each North reply (first 200 characters), the number of turns, the closing summary, the readiness state, and any question asked twice.

**M1.3 Intent is ready (Mei).** Open the intent (`/centre/intent/<iid>` or the project's Intent step). Check the closing summary: it names the missing sections, if any. Do not sign anything. Record the readiness state.

Press **Send to build** only when the summary has no missing section. The route is `POST /api/v1/intents/<iid>/send-to-build` [the button label is on screen].

**M1.4 Sign the intent (Daniel).** Sign in as Daniel. Open **Action** (`/centre/action`); find the card "Intent to sign" (the UC4 card name). Open it. Read the figures and definitions on the page. Tick the confirmation box ("I have read all..."; label on screen) and press **Sign intent**. Route: `POST /api/v1/intents/<iid>/sow/sign` with body `{"confirm": true, "version": <n>}`.

Expected: the intent is signed and read-only. The definitions read as in M1.2. Record the signature line text, the version and the time.

**M1.5 Hand over to the data engineer (Mei, then Leo).** As Mei, open `/centre/build/p/<pid>/handover`, pick **Leo Park**, set a due date, write a note (for example: "Leo, July first; the Excel and CSVs come by upload; the notices are PDFs, two per month; check against my figures in the answer note."), press **Hand over to Leo Park**. Sign in as Leo and open **Action**. Expected: Leo sees the project. Record the due date and the note as it appears to Leo.

**M1.6 Architecture: confirm the systems (Leo, Span).** Open `/centre/build/p/<pid>/architecture`. Span shows each source as the intent recorded it. For each of the five sources, press **Confirm** (route `POST /api/v1/build/p/<pid>/architecture/systems/confirm`). Span must not ask for something the intent already said; if it does, record it.

**M1.7 Architecture: the few questions (Leo, Span).** Span asks only what the intent and the scan do not answer, each with a default. Accept the defaults one by one, or press **Accept all** (`POST .../architecture/questions/accept-all`). For grain, use "monthly by fund and by entity" (the answer key shows both; record which Span proposed). Record the questions asked and the defaults.

**M1.8 Samples (Leo).** On the Samples tab:
- Upload the commitments schedule `docs/demo/uc6/sources/2026-07/commitments_schedule_2026-07-31.xlsx` (table sample), and the three bank CSVs, the administrator CSV and the notice receipt log from `docs/demo/uc6/sources/2026-07/`.
- For the notice receipt log (header only, no rows), accept Span's reading and record it.
- July has no PDFs.

Expected: each file is profiled. Record each file's row count and each rejected file with its message. Mark columns with `POST .../samples/<sid>/mark` only if Span asks.

**M1.9 Mapping check (Leo).** Read the mapping lines for the commitments file. **Check specifically** that the manager call-plan columns (sheet "Commitments", columns N and O, the estimates) are not mapped as calls, and that the "Notices" sheet is not read as the call list. Expected: estimates are not due (UC6-05). [risk R2] Span may map N and O as calls. Record the mapping line for each column N and O, verbatim.

**M1.10 Capital-call schedule: the model change (Path P, decision D1).**
- Path P: Span has no silver table for the calls (UC6-12). Span's chat drafts gold tables only [risk R3]. Ask Span in the chat to propose a silver schedule: type `Please propose a silver table for the capital call schedule: fund, amount, due date, status (noticed or confirmed), notice reference, superseded flag, cycle. Put it in the pack as a model change.` Record Span's reply verbatim.
- If Span has no path, the data engineer proposes the model change with `POST /api/v1/model/proposals` (body `{"add_table": {...}, "note": "..."}`; the exact shape is in `e0a_catalogue.propose`) or with `POST /api/v1/build/p/<pid>/plan/propose` and `model_change`. Record the route used.
- Anita approves the model change: as Anita, `POST /api/v1/model/proposals/<n>/approve` (head_of_data seat) or the "Model changes" panel in Build. Anita must not be the proposer (the product refuses it). Record the approval line.
- Path K (D1-K): no model change. Record that the calls come from the Evidence path (M5.4 onward) and that Span did not need a silver table.

**M1.11 Design pack (Anita; Leo drafts).** Leo: press **The design pack** (tab) > **Draft the design pack** (`POST .../architecture/pack/generate`). Read the tabs Target model, Catalogue, ETL mapping sheet, Rules, Sources. Settle any open row with a note. Press **Send to the head of data for approval** (`POST .../pack/submit`). As Anita, press **Approve version 1** (`POST .../pack/approve`).

Expected: pack version 1 with 4 or 5 sources (`commitments`, three bank files, administrator cash, notices), gold tables for the liquidity view, and the rules: estimates never due, one call per call reference, confirmed-only called, administrator cash. Record the version, the source count, the open rows and each rule text as shown.

**M1.12 Build plan (Leo proposes, Anita approves).** Leo: **Draw the build plan from this pack** (`POST .../pack/plan`, then `POST .../plan/propose`). Anita: **Approve** on the plan (`POST .../plan/approve`). The product refuses Leo as approver. Record the plan version and the approver line.

**M1.13 Builder: run on a copy (automatic, Leo).** The builder starts on approval (`on_approved`). Open `/centre/build/p/<pid>/pipelines`. Expected: the builder's thread shows connections for each source (uploads, as the pack says), a copy run, and a benchmark request. Do not press anything the builder has not asked for. Record the run ID of the copy run from `GET /api/v1/build/p/<pid>/runs` and from Operations.

Check the copy's figures against July (answer key section 3.1): cash EG-HOLD 2,305,906.48; EG-TRUST 1,252,492.34; EG-B 905,000.00; calls due within 30 days none in all three entities; commitment 44,000,000.00; called 30,550,000.00; uncalled 13,450,000.00; outstanding 0.00. Record each figure as shown, and the screen it came from.

**M1.14 Benchmark (Leo).** The builder asks for last month's report. July has none (no earlier report exists). Answer the question with "no earlier report" in the benchmark box, or press the control that says so [verify label]. Record the builder's reply verbatim. Expected: the builder does not block; it records that no benchmark was checked. [risk R4] If it blocks, record it as blocking for M1.15.

Then compare the copy figures with the answer key figures in M1.13 by hand and record each difference. Any difference is an issue (section 9).

**M1.15 Verify (control totals, Leo then Raj).** Open the verify step (`GET /api/v1/build/p/<pid>/verify`). Mark the control totals (`POST .../verify/mark`), send (`.../verify/send`). As Raj, accept (`.../verify/accept`). Record the checks shown ("0 of 1" was a UC4 gap; record if it recurs).

**M1.16 Go live (Leo).** Leo presses **Go live** in the builder (`POST /api/v1/build/p/<pid>/builder/go-live`). Expected: the live run is a PRODUCTION run, and the project is live. Record the run ID and its badge in Operations (`/centre/operations`, section Runs).

**M1.17 Starter dashboard (Lumen; Mei submits; Daniel approves).**
- Lumen proposes the starter when the pipeline goes live (`POST /api/v1/build/p/<pid>/studio/starter`). Mei opens the dashboard studio for the project [verify label, "Dashboard studio"].
- Expected tiles, from the signed intent: cash after calls (each entity), calls due in 30 days, shortfall, called and uncommitted by fund, and the checks line. Record each tile's value, unit and source.
- Mei presses **Send for approval** (`POST .../studio/<did>/submit`). Daniel opens Action, reads "What Lumen checked", presses **Approve** (`POST .../studio/<did>/approve`).
- [risk R5] Expected: the approval panel names the run and the signed version. A raw fraction (0.0417) where the intent says percent is a finding.

**M1.18 Month 1 Action and Consume (Mei, Raj, Sofia).**
- Mei opens Action. Expected for July: no "Fund the capital call" case; one match item for the 23 Jul payment of 300,000 with no notice on file (UC6-01). [risk R6] Record every item and its wording. The product has no "unmatched outflow" type that I found (section 10); record where the item appears, or that it does not.
- Raj opens Consume, Office view (`/centre/consume/office`). Read Liquidity: available cash, due in 30, 60 and 90 days, cash after calls, uncommitted, not confirmed. Expected for 31 July: EG-HOLD 2,305,906.48, EG-TRUST 1,252,492.34, EG-B 905,000.00, no calls due. Record the figures and the `as_of` used. The route: `GET /api/v1/office/liquidity?currency=USD&as_of=2026-07-31`.
- Sofia reads the same page (read only). Record what she can see.

---

## 6. Months 2 to 4: the monthly routine

This is what a real person does each month. August, September and October are run in order. Each month has the same steps; the figures are in section 6.1. Do not skip a step because the previous month was clean.

**The monthly routine**

R.0 **Set the cycle date.** Write the cycle's as-at date on the run log line (for example 2026-08-31). Path K reads it with `as_of=`. Path P runs on the company clock (decision D2) [risk R7].

R.1 **Receive the files (Leo).** The month's files are the ones in `docs/demo/uc6/sources/<YYYY-MM>/`. Upload them through the UI, in this order:
1. Intake: `/centre/data/intake?project=<pid>`, control **Upload a file**. Upload the commitments schedule (`commitments_schedule_<as-of>.xlsx`), the three bank CSVs (`bank_cash_EG-HOLD_<YYYY-MM>.csv`, `bank_cash_EG-TRUST_<YYYY-MM>.csv`, `bank_cash_EG-B_<YYYY-MM>.csv`), `administrator_cash_<YYYY-MM>.csv` and `notice_receipt_log.csv`. For October, the bank files are named `bank_cash_EG-B_2026-10.csv` and so on; the folder has the same names.
2. Each uploaded file: open it (the file page), press **Profile** if shown, read the mapping, press **Accept** on each column that is right, then **Load this file** (`POST .../intake/files/<id>/load`). Record the file's state and its control totals.
3. Evidence: `/centre/evidence` [verify the upload control label]. Upload each notice PDF for the month, one at a time. For August: `2026-07-06_cedarpoint_fund-D_call.pdf`. For September: `2026-09-01_cedarpoint_fund-D_distribution.pdf`, `2026-09-15_saltmarsh_fund-E_call.pdf`, `2026-09-29_saltmarsh_fund-E_call-amended.pdf`. For October: `2026-10-01_cedarpoint_fund-D_call.pdf`, `2026-10-02_cedarpoint_fund-C_call.pdf`, `2026-10-05_northgate_fund-A_distribution.pdf`, `2026-10-06_saltmarsh_fund-E_call.pdf`.
   - Record for each: the document ID, the extraction result and the fields found (`GET /api/v1/evidence/documents/<id>/fields`).
   - [risk R8] The intake does not take PDFs, and the Evidence upload is per document. A monthly batch of notices is a hand job. Record the number of clicks.

R.2 **Confirm the notice fields (Mei).** On the Evidence page, for each notice:
- Read the fields: fund, amount, due date, notice kind, manager reference.
- Press **Confirm** (`POST /api/v1/evidence/fields/<id>/confirm`) only when the field matches the PDF. Use **Correct** (`.../correct`) when a field is wrong. Use **Reject** (`.../reject`) for a notice that is not a call.
- Do not confirm the Saltmarsh notice of 6 Oct (UC6-07; it is not confirmed in the answer key). Leave its status as "noticed". Record that you left it.
- Confirmation writes a confirmed call and, if due within 30 days, opens a "Fund the capital call" case (`k6_liquidity.alert_if_due`). Record each case ID.

R.3 **Run the pipeline (Leo).** Open `/centre/build/p/<pid>/pipelines`. Press **Try it on a copy** (sandbox run, `POST /api/v1/build/p/<pid>/run?mode=sandbox`). Read the steps. Then press **Go live** only if the copy is clean (`POST .../run?mode=live`). Record the run IDs of both runs.

R.4 **Read the run in Operations (Leo).** Open `/centre/operations`, section **Runs**. Each run shows a TEST or PRODUCTION badge, its trigger and its steps. API: `GET /api/v1/ops/runs?mode=production` and `GET /api/v1/ops/runs/<run_id>`. Record the run ID, the badge, the trigger and the steps (rows and status per table).

R.5 **Verify (Leo, then Raj).** Verify step as in M1.15. Raj accepts the control totals.

R.6 **Action (Mei, Raj, Sofia, Anita).** Open `/centre/action`. For each item, record the wording, the figures in it, the owner and the buttons offered. Expected cases per month: section 6.1.

R.7 **Each person acts on what names them.** Use only the buttons the screen offers; record each press (case ID, person, button, the screen after):
- Mei: match a payment to a notice; log a late receipt; confirm the notice (R.2); close a timing break as timing (**Close as timing**, case `dismiss` with the timing cause).
- Raj: approve the 30-day view and any funding decision (**Take the case**, then the approval the case offers, `POST /api/v1/cases/<cid>/approve`).
- Sofia: read the amendment and the unconfirmed call (read only).
- Anita: rule on a manager estimate against a notice if the case asks (UC6-05). Record her answer as a rule proposal, not as a case action.

R.8 **Read Consume (Raj, Daniel).** Open `/centre/consume/office`. Read Liquidity for the cycle's as-at date (`as_of=` in the URL or the API). Record the figures, and use the "why" or source line on each figure (the screen shows source tables; record them). Compare with section 6.1.

R.9 **Check the run IDs.** The figures on Consume must come from the run that just finished. Record any figure with no run ID, or with an older run ID, as a finding (R9).

R.10 **Write the month's line in the run log** (section 8): the figures as shown, the run IDs, the pass or fail against 6.1, and the issues raised.

### 6.1 Expected results by cycle (answer key)

**August (as at 31 Aug).** Cash: EG-HOLD 2,287,630.12; EG-TRUST 1,199,690.58; EG-B 654,014.07. Calls due within 30 days: none. Calls 31 to 60 days: none. Commitments unchanged: called 30,550,000.00; uncalled 13,450,000.00; outstanding 0.00.
- UC6-02: Cedarpoint Opportunities II 300,000, notice dated 6 Jul, received 12 Aug (receipt log). Matched to the 23 Jul payment: shown as paid and late. No open call. Late receipt logged, not a shortfall.
- UC6-03: 14 Aug EG-B sweep of 221,872.96 to the investment account. Not a call, not a shortfall; EG-B cash falls by that amount.
- UC6-01 is still open: the 23 Jul payment of 300,000 has no notice. The notice received 12 Aug (UC6-02) closes it. Record whether the product matched them.

**September (as at 30 Sep).** Cash: EG-HOLD 2,259,000.00; EG-TRUST 1,175,000.00; EG-B 875,200.00.
- UC6-04: Saltmarsh Infrastructure Fund II noticed 550,000 (15 Sep), amended to 600,000 (29 Sep, reference SIF2/CALL/2026/09A-R1). Use 600,000 only. Due 30 Oct. After confirmed calls: 875,200.00. After all noticed calls: 275,200.00 (fundable).
- UC6-05: commitments file call-plan estimates (Cedarpoint Opportunities II 250,000 on 4 Dec 2026; Saltmarsh 600,000 on 25 Jan 2027) are never due and in no bucket.
- The Cedarpoint Opportunities II distribution of 180,000 (notice 1 Sep, received 3 Sep) is cash already; not a liquidity inflow in this run.
- Commitments (30 Sep): called 30,550,000.00; uncalled 13,450,000.00; outstanding notice 600,000.00 (Saltmarsh, amended). Saltmarsh called stays 4,000,000.00 (not confirmed).

**October (as at 9 Oct; cash to 8 Oct).**

| Entity | Available cash (administrator, 8 Oct) | Calls due 30 days | Calls 31 to 60 days | Cash after calls |
|---|---|---|---|---|
| EG-HOLD | 2,300,000.00 | none | none | 2,300,000.00 (Northgate 320,000 distribution, 16 Nov, is a 60-day inflow, not counted) |
| EG-TRUST | 1,150,000.00 | none | none | 1,150,000.00 |
| EG-B | 880,400.00 | 1,050,000.00: Cedarpoint Ventures III 450,000 (due 20 Oct, confirmed 2 Oct); Saltmarsh 600,000 (due 30 Oct, noticed, not confirmed) | 250,000.00 (Cedarpoint Opportunities II, due 4 Dec, confirmed). Cumulative 60-day calls 1,300,000 | after confirmed 30-day calls **430,400.00**; after all noticed 30-day calls **-169,600.00 (shortfall)**; after confirmed 60-day calls 180,400.00; after all 60-day calls -419,600.00 |

- UC6-06: Entity B shortfall -169,600 after all noticed calls. Finance case "Fund the capital call" for Cedarpoint Ventures III (450,000, due 20 Oct). No Finance case for Saltmarsh (not confirmed).
- UC6-07: Saltmarsh 600,000 noticed 6 Oct, not confirmed. Listed under "not confirmed yet"; in the all-noticed view only.
- UC6-08: the 6 Oct Saltmarsh notice repeats the 29 Sep amendment (same reference, same 600,000). Counted once: 30-day calls 1,050,000, not 1,650,000.
- UC6-09: bank EG-B 868,000.00 on 8 Oct against administrator 880,400.00. The 12,400 wire (WIRE-20261008-B01, legal fees) left the bank on 8 Oct and the administrator booked it on 9 Oct. Over the 5,000 tolerance: a break, closed as timing. Official figure is the administrator's. Bank-based shortfall would be -182,000 (for the record only).
- UC6-10: Saltmarsh manager paid-in 4,600,000 against office confirmed called 4,000,000. Cedarpoint Ventures III called 4,050,000 includes the 450,000 not yet paid. Called is confirmed, not paid.
- UC6-11: Northgate 320,000 distribution (notice 5 Oct, payment 16 Nov) is an inflow, never a call.
- UC6-12: no silver table for the capital-call schedule (M1.10).
- Commitments (9 Oct): A 15,000,000 / called 11,250,000 / uncalled 3,750,000; B 8,000,000 / 7,200,000 / 800,000; C 6,000,000 / 4,050,000 / 1,950,000; D 5,000,000 / 4,750,000 / 250,000; E 10,000,000 / 4,000,000 / 6,000,000, with outstanding notice 600,000. Totals: commitment 44,000,000; called 31,250,000; uncalled 12,750,000 (with the 600,000 outstanding shown separately).

**Check on called totals.** Called went from 30,550,000.00 (30 Sep) to 31,250,000.00 (9 Oct): 30,550,000 + 250,000 (Cedarpoint Opportunities II, confirmed 1 Oct) + 450,000 (Cedarpoint Ventures III, confirmed 2 Oct) = 31,250,000. Record what the product shows and check it against the commitments rows in the Excel, not against this note.

---

## 7. Milestone screenshots

Save each to `.sh-tmp/testenv/uc6/shots/<name>.png` (full page where the screen scrolls). Do not show credentials in any screenshot.

| Name | Screen | When |
|---|---|---|
| G1-action, G1-office | Action and Consume Office before any upload | Gate G1 |
| M1-02-north | North's closing summary | After M1.2 |
| M1-04-sign | Sign page with definitions | M1.4 |
| M1-08-samples | Samples tab with the July files | M1.8 |
| M1-11-pack | Design pack, Rules and Sources tabs | M1.11 |
| M1-12-plan | Plan approved | M1.12 |
| M1-13-copy | Builder thread and copy figures | M1.13 |
| M1-16-live | Operations, Runs, the live run | M1.16 |
| M1-17-starter | Starter tiles and "What Lumen checked" | M1.17 |
| M1-18-consume | Consume Office, Liquidity, July | M1.18 |
| M2-R2-evidence | Evidence page with the August notice | R.2 |
| M2-R6-action | Action, August | R.6 |
| M3-R6-action | Action, September, including the Saltmarsh amendment | R.6 |
| M4-R6-action | Action, October: fund-the-call, not-confirmed, timing break, the duplicate | R.6 |
| M4-R8-consume | Consume Office, October liquidity | R.8 |

---

## 8. What to record

**Run log**, one JSON line per step, in `.sh-tmp/testenv/uc6/run-log.jsonl`:

```json
{"step": "M1.13", "who": "Leo Park", "month": "2026-07", "action": "Builder copy run", "via": "UI | API POST /api/v1/build/p/<pid>/run?mode=sandbox", "expected": "EG-B cash 905000.00", "observed": "...", "run_id": "run-20261012-131500-ab12", "evidence": "shots/M1-13-copy.png | api/M1-13.json", "result": "pass | fail | prediction-confirmed | prediction-not-seen", "issue_id": "UC6-T-001 or none", "secs": 0}
```

**Issues log**, in `.sh-tmp/testenv/uc6/issues.md`: id (`UC6-T-###`), step, month, role, severity (1 blocking to 4 cosmetic), what happened, what was expected, evidence (screen, API response file, run ID), the answer-key ID if any (UC6-01 to UC6-12), and whether it blocks the next step.

**Path comparison (D1-both)**: for each month and each figure, two columns: Path K (`/api/v1/office/liquidity`) and Path P (the builder or Consume figure). Mark agree or differ, and record the difference.

**Figures**: copy each figure exactly as shown with its currency and unit. Compare with section 6.1 in code (a small script), not by eye.

**API responses**: keep JSON in `.sh-tmp/testenv/uc6/api/<step>.json`. Remove any password or token before keeping it.

---

## 9. Run plan summary

| Cycle | Steps | Expected blocking points |
|---|---|---|
| Gate | G1.1 to G1.4, decisions D0 to D4 | Seeded October answer (G1) |
| Month 1 (July) | M1.1 to M1.18 | Span's silver schedule (M1.10), benchmark with none (M1.14), starter approval (M1.17) |
| Month 2 (August) | R.0 to R.10 | Late notice matching (UC6-02), the 14 Aug sweep (UC6-03) |
| Month 3 (September) | R.0 to R.10 | Amendment and superseded amount (UC6-04), estimates (UC6-05) |
| Month 4 (October) | R.0 to R.10 | Shortfall and cases (UC6-06), duplicate (UC6-08), bank vs administrator (UC6-09), called vs paid (UC6-10), distribution (UC6-11) |

---

## 10. Predicted risks (predictions, not results)

Each is checked and recorded as confirmed, not seen, or a different result. A prediction is never a pass.

- **R0 Mei's role.** The seed credentials file lists Mei as `analyst`; ROLE1 says `owner`. Check the Settings count (section 4).
- **R1 North's definitions.** The sign or unit may be wrong (for example, points versus percent). Check the sign page.
- **R2 Commitments columns N and O (UC6-05).** Span may map the call-plan estimates as calls. Check the mapping line.
- **R3 Span's silver table.** Span's tools draft gold tables only (`docs/plan/v6-landings/DM1-data-model-view.md`). A silver schedule may not be produced by Span; the data engineer may have to propose it.
- **R4 No prior benchmark.** The builder may block when no earlier report exists.
- **R5 Starter and approval.** The starter may repeat a tile, show a raw fraction, or show "No reviewed run is on record".
- **R6 Unmatched outflow (UC6-01, UC6-03).** The product has no type for a payment with no notice or for a treasury sweep (the builder's explained variance covers only revisions of valuations, `V6-builder.md` open items). Expect the item to appear as a figure or case with no clear owner.
- **R7 Clock.** Path P runs on the company clock (9 Oct). Path K uses `as_of=`. Check that July, August and September figures change with `as_of`, and that the pipeline's figures do not.
- **R8 PDFs by hand.** The intake takes no PDFs. The Evidence upload is one document at a time. Count the clicks per month.
- **R9 Run IDs on Consume.** A Consume figure may carry no run ID. Check the source line and the run ID against Operations.
- **R10 Duplicate and amended notices (UC6-04, UC6-08).** Check that Saltmarsh counts 600,000 once and that the 6 Oct notice is not a second call. Path K keys on the document; check whether two documents with one reference are counted twice.
- **R11 Bank or administrator cash (UC6-09).** The product may use the bank balance (868,000). `k6_liquidity._cash` prefers the administrator view; check which figure the screen shows.
- **R12 Distribution as inflow (UC6-11).** Check the Northgate 320,000 is not added to cash or to calls. Path K treats distributions as their own kind.
- **R13 Called vs paid (UC6-10).** The manager's paid-in (4,600,000) may replace the office called figure (4,000,000). Check the commitments view.
- **R14 Fund-the-call case.** Path K opens the case on confirm within 30 days. Check it opens for Cedarpoint Ventures III on confirm (2 Oct) and not for Saltmarsh (not confirmed). The case may already exist from the seed (G1).
- **R15 Estimates (UC6-05).** I did not find a rule in `k6_liquidity.py` that separates a manager estimate from a notice (the module header and the `forecast` contract). Expect the estimate to be ignored only if the commitments import leaves it out.

---

## 11. Review: what is missing, and what I recommend

This is the honest view from reading the code and the answer key. Each item is a product question, not a test result. Items 1 to 3 should be decided before the first run.

1. **Two capital-call engines (blocking decision).** Path K (`k4`/`k6`, Consume Office) already holds commitments, notices, confirmation, the 30/60/90 forecast and the "Fund the capital call" case. The brief asks Span to draft a second, silver, capital-call schedule. Two sources of truth would disagree at some point. **Recommend:** keep Path K as the one calls engine; make the pipeline feed it (cash and commitments files), and drop the silver schedule unless Path K cannot hold a fact the answer key needs.
2. **No as-of date in the monthly build.** The pipeline, the builder and Lumen run on the company clock, pinned to 9 Oct in the demo. Only the liquidity route takes `as_of`. A month cannot be re-run as it was known then (`cutoff` is not exposed). **Recommend:** an as-of and cut-off on the run, and a way to set it in the UI for demos and back-tests.
3. **Notices do not land monthly.** The intake takes Excel and CSV only; the Evidence path reads one PDF at a time and confirms each field by hand. Four to five notices a month means a hand job with no batch view, no "notices received this month" checklist, and no missing-notice alert. **Recommend:** a notice inbox per project: drop the month's PDFs, see which are read, which are confirmed, which are missing against the commitments.
4. **Monthly arrival is not a trigger.** A monthly schedule runs at its time on the server clock. Dropping the month's files starts nothing, except for `on_arrival` schedules. Nobody is told that a source for the month has not arrived. **Recommend:** a "files due this month" checklist on Action, with an alert at the cut-off.
5. **No unmatched-payment type.** A payment with no notice (UC6-01) and a treasury sweep (UC6-03) have no type I could find. The builder's explained variance covers only valuation revisions. **Recommend:** a transaction classification rule in the pack (call, distribution, treasury transfer, unmatched) with an owner, before any figure is built on it.
6. **Estimates and amendments.** I found no rule that keeps a manager's estimate out of the due calls, and no rule that counts an amended notice once by its reference (UC6-04, UC6-08). **Recommend:** key a call on its manager reference; a later notice with the same reference supersedes the earlier one; estimates are a separate kind that never enters a bucket.
7. **Benchmark for a liquidity view.** The builder benchmark is built for return reports. A liquidity report with "label then number" lines may work, but there is no prior report in the sources. **Recommend:** accept a "previous view" as the benchmark when no report exists, and say so on the screen.
8. **Two different starter checks.** The starter's "checks" tile is text, not a table (`V6-lumen-starter.md`). A figure that fails a check cannot be seen as a failed tile. **Recommend:** a table of checks per run, which the starter can read.
9. **The demo seed answers UC6.** The universe holds the October figures and the case (G1). A demo will look right whether or not the build works. **Recommend:** a UC6-clean seed option (Option A) before any UC6 demo.
10. **Small items seen while reading (not UC6-specific).** `b6_routes._seat` words the architect seat (used for go-live) as "head of data"; check which seat the go-live button really needs before a tester is told so. Recheck the role matrix after any role change (`ROLE1-roles-and-menus.md` says Mei is owner; the seed file says analyst).

---

## 12. Done means

- Gate G1 and decisions D0 to D4 are recorded.
- Every step in sections 5 and 6 has a run-log line, and each figure in 6.1 has been checked in code.
- Every risk R0 to R15 is marked confirmed, not seen, or different, with evidence.
- Each issue has an entry with severity and what it blocks.
- The month's run IDs appear in Operations, and each Consume figure has its run ID or a recorded reason it has none.
- The 8811 server is stopped. Nothing was written to the repo `data/` folder, to ports 8400, 8504 or 8200, or to product code. No commit, no push.

Report to Nitin: the gate decisions, the number of steps run, the issues by severity, the path comparison (D1-both), and the answer to one question: can a business owner run UC6 each month with no engineer, and if not, which step needs one?
