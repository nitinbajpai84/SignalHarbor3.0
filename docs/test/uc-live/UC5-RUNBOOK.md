# UC5 runbook: run the limit-monitoring test again

How to repeat the UC5 live test (Evergreen Office, July to October 2026) on your own port, in about an hour. Findings and fixes: `UC5-REPORT.md`. The full step list with expected figures: `UC5-PLAN.md`.

## 1. Before you start

- Testing models only. Never switch to Real use.
- Do not touch the repo `data/` folder or ports 8811, 8813, 8400, 8504, 8200, 8697. Use port 8812 (or your own).
- Temp files go to `D:/Temp/uc5/`. Never print a password; the helper reads them from the seeded credentials file.
- Python: the interpreter named in `.sh-tmp/uc4w/py.sh`. Below it is `PY`.

## 2. Fresh environment

Run in Git Bash from the repo root:

```bash
export TMP=/d/Temp TEMP=/d/Temp TMPDIR=/d/Temp PYTHONIOENCODING=utf-8; unset DATABASE_URL REDIS_URL SH_ALLOW_REAL_MODE
```

```bash
PY tools/seed_demo_boot.py --reset --data-root ".sh-tmp/testenv/uc5/data"
```

Build the UI into the tester's own folder, so other testers' screens are not changed:

```bash
cd ui && npx vite build --outDir ../.sh-tmp/testenv/uc5/dist --emptyOutDir
```

Start the server detached, from PowerShell (a server started from a tool's background shell stopped twice in this run):

```bash
powershell -File ".sh-tmp/testenv/uc5/restart.ps1"
```

It stops whatever listens on 8812, starts `tools/serve_test.py --port 8812 --data-root .sh-tmp/testenv/uc5/data --dist .sh-tmp/testenv/uc5/dist` and prints 200. The server log is `.sh-tmp/testenv/uc5/server.log`.

## 3. The helper scripts (in `.sh-tmp/testenv/uc5/`)

| Script | What it does |
|---|---|
| `uc5lib.py` | `W(person)` signs in one person in a headless browser; `.api(method, path, body)` calls the API with that session; `.go(path)` and `.shot(name)` for screens; `up()` uploads a file; `counts()` reads warehouse row counts; `sj()` saves JSON to `D:/Temp/uc5/` |
| `m1_chat2.py "<text>" …` | Mei's turns in the North chat for the intent |
| `act.py <person> <case id> <action> '<json>' [x <shot>]` | One case action (get, take, note, submit, approve, ask_finance, resolve, dismiss) |
| `chain.py <xlsx> <source code> <tag> [mapping to withdraw]` | Upload, first load, show the proposed mapping, Anita approves, load again |
| `nofooter.py <src> <dst>` | Copy of a positions workbook without the "Portfolio totals" block (data-quality workaround W-1) |
| `month2.py <YYYY-MM> <tag> <benchmark txt or ->` | A month: upload both files, profile, load, benchmark, test run, live run |
| `golive.py` | Go live (variance accepted) and one live run |
| `limits.py <as-at> <cutoff> <tag> <person>` | Limits check by API, saved to `D:/Temp/uc5/<tag>_limits_api.json` |
| `screenrun.py <as-at> <shot> <person> <received by, local time>` | The same check on the Reconciliations screen with Run now |
| `cases.py <person> <tag>` | The limit cases with status, owner and closing reason |

Every call is appended to `D:/Temp/uc5/calls.jsonl`.

## 4a. Month 1 as run 2 did it (13 Oct, after the G-1 and G-2 builds)

Scripts in `.sh-tmp/testenv/uc5/` (evidence to `D:/Temp/uc5/r2/`; the helper now keeps one browser and a session per person):

1. Grace: Settings > People and access, set Sofia Reyes to Owner.
2. `PY r2_intent.py` (Mei and North), then Daniel signs and sends to Build; Mei assigns the three steps to Leo.
3. `PY r2_arch.py` (Leo: sources, samples, grain).
4. `PY r2_load.py D:/Temp/uc5/r2/edited/administrator_positions_2026-07-31.xlsx month_end_positions_work jul_pos` (footer removed first with `nofooter.py`), then the same with `"Latest statements"` as the last argument. Anita approves each proposed mapping (Valuation date must map to the position date; withdraw any mapping that maps a second column onto the same field) and the 27 names.
5. `PY r2_pack.py`: pack (settle the signed-limits row), the `limit_results` model change (Leo proposes, Anita approves), plan from pack, Sofia's 6% version signed by Daniel. Then `PY r2_build.py`: regenerate the pack so it reads `limit_results`, plan, test run, Go live with "no benchmark".
6. Limits: `PY screenrun.py 2026-07-31 r2-07-jul-limits-screen mei` (no received-by time: in a replay the files' receipt time is their upload time, so a past cutoff hides them).
7. Dashboard: `PY r2_dash.py` (live run, starter, approve). Remove any tile that adds shares together with the layout editor, submit, approve.
8. Cases and delivery as in step 13 below.

## 4. Month 1 (July): build (run 1)

1. People: Grace opens Settings > People and access and sets Sofia Reyes to Owner (the risk owner must act on cases).
2. Intent: Mei starts a project in Build with the message in `UC5-PLAN.md` M1-05, answers North (readers, access "Internal to the listed readers", the process steps, the four limit figures, the rules, success, documents none). Daniel signs it and sends it to Build.
3. Handover: Mei assigns Architecture, Pipelines and Dashboards to Leo (a due date in the future).
4. Architecture: Leo confirms both sources, uploads the July positions and limits workbooks as samples, answers grain "monthly by portfolio", accepts the rest.
5. Mappings first: Leo uploads the footer-less July positions copy (`chain.py`). The first load proposes a mapping; Anita approves it (Valuation date must map to the position date); the second load writes 27 rows. Anita approves the 27 instrument names the first time a new source is used (Settings > Identifiers).
6. Pack: Leo generates and submits the design pack; the signed-limits sample row is settled ("kept in the rules register"). Anita approves it.
7. Plan: Leo uses Plan from pack (Architecture page). Anita approves it. Schedule: monthly, 5th business day, 06:00.
8. Limit version: Sofia proposes the signed v1 maximum of 6% for Harborview Semiconductor, effective 1 Jan 2026. Daniel signs it.
9. Builder: Leo gives the benchmark (one "label: number" per line, file name with .txt). Test run, recheck. The variance is "unexplained" while the pack has no limit table: Anita decides to go live anyway; Leo presses Go live.
10. Limits check: Mei opens Action > Reconciliations, Check as at 2026-07-31, Files received by 4 Aug 2026 14:00 (06:00 UTC), Run now.
11. Dashboard: Leo makes Lumen's starter, accepts and submits; Daniel approves; Daniel opens it in Consume.
12. Delivery: Leo makes an email channel for the three readers; Daniel approves; Leo turns delivery live. Nothing is sent from a test environment.
13. Cases: Sofia takes each breach, notes real or stale, sends it for check with the closing reason; Daniel (or Raj for a cure) approves.

## 5. Months 2 to 4

For each month (receipt times: Aug 2 Sep, Sep 2 Oct, Oct 3 Nov, all 06:00 UTC):

```bash
PY month2.py 2026-08 aug D:/Temp/uc5/jul_limits_report.txt
```

```bash
PY golive.py
```

```bash
PY limits.py 2026-08-31 2026-09-02T06:00:00Z aug mei
```

```bash
PY screenrun.py 2026-08-31 uc5-14-aug-limits-run mei 2026-09-02T14:00
```

Then the cases (`act.py`), as in step 13. September only: before the run, Sofia proposes v2 (5% from 1 Sep 2026) and Daniel signs it. In September Sofia asks Raj in Finance on the Harborview case; Raj approves the trim by note; the case stays open until October, when Sofia sends it for check as "cured" and Raj approves.

## 6. What to compare

Compare each month's run with `ANSWER-KEY.md` (share within 0.01 point, over-by within USD 500), and read the report's section 3 first:
- With the receipt-time cutoff, Cedarpoint and hedge funds differ from the key in July, August and September, because the key uses statements the seed records after that time. Run the check once without a cutoff to see the key's figures.
- October cannot match until gap G-2 is decided (October values do not reach the check).
- Stale ages are counted to the run day (the demo clock is pinned to 9 Oct 2026).

## 7. Finish

- Stop only the 8812 server (`restart.ps1` shows how to find it by port).
- Do not commit. Keep `D:/Temp/uc5/` for the evidence.
