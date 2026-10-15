# Use-case checkers: what each agent expects to fail (read from code, before the data load)

Unrun. `docs/plan/v4-landings/D.md` doesn't exist yet (only K1 to K8 are there), so I didn't seed or serve anything and haven't tested the checker against the product. It compiles clean (`py_compile`), and nothing outside `tools/verify_10uc/` was touched.

**File:** `<repo>\tools\verify_10uc\uc10.py`

**What it does**
- **Logins and routes:** it signs in through `/api/auth/login` as people from the universe `people` list, reading passwords from the creds file without printing or writing them. It calls `/api/v1/build/projects`, `/api/v1/model/projects/{pid}/tables`, and the consume dashboard, tile-data and audience routes.
- **Expectations:** project title, stage, bronze and gold table names, dashboard id, tile ids, titles and K-codes, and the audience all come from the universe JSON. The audience names are parsed out of the P33 `expected` text. Nothing is hard-coded a second time.
- **Outputs:** it writes `DIR/uc10/<fact>.json` and `DIR/uc10/result.md`, and exits 1 on any failure.

**Facts**

| Fact | What it asserts | Status |
|---|---|---|
| P33_project_live | Project is found by title and its stage is "live" | unrun |
| P33_bronze_gold | The 2 bronze and 2 gold table names match exactly | unrun |
| P33_dashboard | `dash-0ad2b1c7` has exactly the 3 accepted tiles (t-000001 to t-000003, titles, K01 to K03) | unrun |
| P33_audience | Audience is exactly Daniel Foo and Raj Patel | unrun |
| P33_tile_data | Each tile's data call returns HTTP 200 with at least one row | unrun |
| P33_access | Daniel, Raj, Leo Park (the maker) and Grace Ong (admin) get 200. Mei Chen, Sofia Reyes and Anita Rao get 403 or 404 on the dashboard, and Mei, Sofia and Anita also get 403 or 404 on tile data. | unrun |

**Failures:** none observed, because nothing ran.

**Likely failures when D lands**
- **Mei, Anita or Sofia not blocked (my assumption).** The planted fact names role "analyst", but the dashboard code only lets the maker, the admin or an audience member view it, so I assume other analysts are blocked. If a non-audience analyst gets 200, that is a product access bug. If you meant analysts to see it, the universe fact is ambiguous.
- **Leo Park not the maker (my assumption).** I treat Leo Park as the maker because the seed sets the data engineer as `created_by`. If `seed_10uc` changes that, P33_access would flag it as a seed problem.

**To run once `D.md` is there**
1. Seed a temp root under `.sh-tmp/verify/uc10/data` with `seed_evergreen.py`, then `seed_10uc.py`, then `seed_v3_demo.py`. Each takes `--data-root` and `--reset`; `seed_v3_demo.py` takes only `--data-root`.
2. The creds file the seed writes is `<root>/_control/seed_credentials.txt`.
3. Serve it with `serve_test.py --port 8659 --data-root ROOT`, run `uc10.py`, then stop the server.

---

File: `<repo>\tools\verify_10uc\uc9.py`

**Run status:** unrun. `docs/plan/v4-landings/D.md` does not exist yet (the folder only has K1–K8), so I did not seed or serve anything. The file passes `python -m py_compile`.

**What it checks for P32**
- **Setup:** it logs in as Daniel Foo (sponsor) and finds the signed intent "Monthly investment report in USD and SGD" through `GET /api/v1/projects`. It then calls `GET /api/v1/intents/{iid}/sop`.
- **Steps:** for each of the 6 steps, name, who, system, control and exception are compared with `10uc_universe.json`. Input and output must be stated (not "Not stated yet").
- **Manual and hand-overs:** manual steps must be `[1,2,3,4]`, and hand-overs must be 1-2, 2-3, 3-4, 4-5, 5-6.
- **Downloads:** `/download?format=md` must contain every step name and four "manual: a candidate for automation" flags. `/download?format=docx` must return a .docx or the .md fallback.
- **Access:** all 7 seeded people must get 200. A signed-out caller must get 401 or 403 on both the preview and the download. An unknown intent id must get 403 or 404.
- **Output:** results go to `DIR/uc9/P32.json` and `DIR/uc9/result.md`, one row per check. Exit code is 1 on any failure. Passwords are read from the creds file and never written out.

**Per-fact status**

| Fact | Status |
|---|---|
| P32 | unrun |

**Expected failures, from reading the code**
- **Input and output may fail.** `seed_10uc.py` only back-fills control, exception and manual from the universe. The SOW steps' `inputs` and `outputs` come from the North conversation. If the seed leaves them empty, the SOP shows "Not stated yet". That would be a seed gap, because the universe does not list per-step inputs or outputs.
- **docx is not testable on this Python.** The venv has no `python-docx`, so the server will serve Markdown for `format=docx`. The checker accepts that, but real .docx output stays unverified.
- **No role is denied.** `k8.permissions.yaml` and the Consumer seat allow all six company roles. The only "should not see it" checks possible are signed-out callers and an unknown intent. If the test plan wants a role refused, the universe or the permissions would be wrong, not the product.

**Assumption to confirm on first run:** the checker assumes the project record from `/api/v1/projects` carries `intent_id`. I did not confirm that the response shape includes it. If it does not, the "signed intent found" check will fail and the lookup needs a different route.

---

`tools/verify_10uc/uc8.py` is written and passes `python -m py_compile`, but it is unrun. `docs/plan/v4-landings/D.md` doesn't exist yet (only K1 to K8 are there), so I didn't seed or serve anything. I didn't touch `data/`, port 8400, `seed_10uc.py` or any other file. The `tools/verify_10uc/` folder already held `uc9.py` and `uc10.py` from other agents.

**File:** `<repo>\tools\verify_10uc\uc8.py`

**Per fact**

- **P28, quantity mismatch on T-20261002-003:** unrun. It expects one break case titled "Trade differs …" with an impact of (12000 − 10200) × 42.15 = 75,870.00. The checker asserts that matches the universe's `difference_usd`.
- **P29, T-20261006-005 missing at the administrator:** unrun. It expects one break case titled "Trade not matched …" with an impact of 592,000.00 USD.
- **P30, FXF-2026-002 confirmation mismatch:** unrun. It expects one break case with an impact of SGD 8,100.00 (or USD 6050.19) and none for FXF-2026-001.
- **P31, matched trades:** unrun. It expects no case for T-20261001-001, T-20261002-002 or T-20261007-006. Any other trade cases are listed as information, not as a failure.

**How the checker works**

- **Login:** it signs in as Mei Chen (analyst) using the creds file. It runs `POST /api/v1/recon/trade_vs_admin/run` for 2026-10-09, then reads `GET /api/v1/cases?exception_type=break`.
- **Access:** Raj Patel (approver), Sofia Reyes (participant) and Daniel Foo (sponsor) must get 403 on `POST /api/v1/recon/trade_vs_admin/run` and 200 on `GET /api/v1/recon/runs` (GET runs is open to every company role; POST run is not). An unauthenticated `GET /api/v1/cases` must return 401 or 403. Any of these failing fails all four facts.
- **Output:** every figure is a Decimal read from `docs/test/10uc_universe.json`. It writes `DIR/uc8/<fact>.json` and `result.md`, and exits 1 on any failure.

**Product behaviour to check on the first real run**

- **FX forward cases:** `_trades` in `e3_recon.py` matches whatever the seed loads as transactions. If `seed_10uc.py` gives the FX rows an external trade id, the titles should contain "FXF-2026-002". The checker finds cases by that id in the case title, so a seed that omits the id would fail P30.
- **Impact currency:** I don't know whether P30's impact comes out as SGD 8,100 or USD 6050.19, so the checker accepts either, each with its own currency.
- **Case visibility:** `e4a.permissions.yaml` lets every company role read `/api/v1/cases`, with access decided in code. The checker only asserts the recon-route 403s and the unauthenticated 401/403. It does not assert that participants can't see the cases, because no spec says they shouldn't.

**To run it once D.md lands:** seed evergreen, then `seed_10uc`, then `seed_v3_demo` into `.sh-tmp/verify/uc8/data`. Serve it with `serve_test.py --port 8657 --data-root` pointing there. Run the checker with `--creds <root>/_control/seed_credentials.txt`.

---

File: <repo>\tools\verify_10uc\uc2.py. It passes `python -m py_compile` and has not been run.

The run was skipped because docs/plan/v4-landings/D.md does not exist yet. That folder only holds K1.md to K8.md. I did not start a server and did not touch seed_10uc.py, port 8400 or data/.

To run it later:
- Seed a temp root with `seed_evergreen.py --data-root ROOT --reset`, then `seed_10uc.py --data-root ROOT --reset`, then `seed_v3_demo.py --data-root ROOT`.
- The creds file is ROOT/_control/seed_credentials.txt.
- Serve with `serve_test.py --port 8651 --data-root ROOT`, then run `uc2.py --base http://127.0.0.1:8651 --creds <that file> --out DIR`.

**P08 facts checked (all unrun):**
- **run_checked_3_breaks_1:** unrun. The analyst runs `POST /api/v1/recon/cash_by_entity/run` for 2026-10-08 and expects 200, 3 entities checked, 1 break, and 0 or 1 case opened. Zero is fine because the seed already opens the case, and a re-run does not open a second one.
- **break_case_analyst** and **break_case_approver:** unrun. Each role's `GET /api/v1/cases?exception_type=break` must show exactly one case titled "Cash differs · Entity B · 2026-10-08". It must be a `break` in USD with an amount of 12400.00 (compared as Decimal). Its description must contain 880,400.00 and 868,000.00. All figures come from the universe JSON.
- **no_case_trust_holdings:** unrun. No cash case exists for Evergreen Family Trust (1,800, inside tolerance) or Evergreen Holdings (equal at 2,300,000).
- **one_break_case_8_oct:** unrun. Exactly one cash break case is dated 8 Oct.
- **approver_cannot_run_recon** and **participant_cannot_run_recon:** unrun. Both roles get 403 on the recon run and 200 on `GET /api/v1/recon/runs`. GET runs is open to every company role; POST run is not (e3b.permissions.yaml allows only company_admin and analyst).
- **participant_case_hidden:** unrun. The participant gets 403 or no P08 case in the case list.

**Limits:**
- Trust and Holdings figures (1,150,000 vs 1,148,200 and 2,300,000) are only checked indirectly, through "3 checked, 1 break, no case for them". No route exposes per-entity cash numbers.
- `participant_case_hidden` assumes the participant has no grant on Entity B. If it fails, check the seed's entity grants before blaming the product.
- Case visibility for the approver also depends on the same grants. Raj has no grant on Entity B in what I read, so `break_case_approver` is the likeliest false failure.

Nothing has failed, so there is no blame to assign yet.

---

I wrote the checker but did not run it. `docs/plan/v4-landings/D.md` doesn't exist yet (only K1.md to K8.md), so I only did a `py_compile` syntax check. All three facts are **unrun**.

File: `<repo>\tools\verify_10uc\uc4.py`

I didn't touch the seeds or product code.

**Facts**
- **P14: unrun.** As the approver it reads `GET /api/v1/benchmarks/comparison?portfolio=EG-LIQUID&code=EG-OFFICE-BLEND&start=2026-09&end=2026-09` and expects portfolio 4.1667, blend 2.7072, components 3.5002 / 0.4002 / 3.7502 (3.7466 tolerated until the seed spread is settled), difference 1.4595, `liquid_sleeve.difference` 1.9065 and certified true.
- **P15: unrun.** As the approver it reads `GET /api/v1/benchmarks` and expects version 2 to carry the notice "In progress: not used for certified figures." and a `policy_question` with the open case. The approver cannot see the case in `/api/v1/cases`, so that list (`exception_type=policy_question`) is read as Mei Chen (analyst). A request with no session must get 401 or 403.
- **P16: unrun.** It checks that 57,600,000.00 × 1.3412 equals 77,253,120.00 SGD. It also needs the approver's `/api/v1/office/issued` response to show 77,253,120.00 in SGD and 57,600,000.00 in USD. A request with no session must get 401 or 403.

**Likely failures once it runs**
- **P14 and P15 now read the benchmark routes** (`/api/v1/benchmarks` and `/api/v1/benchmarks/comparison`). The 1.9065 figure is read off `liquid_sleeve.difference` (the 60/40 liquid sleeve), not off `difference` (against the blend, 1.4595).
- **The wording of the P15 case is a guess.** The seed's case text is not in the universe, so it may need loosening if the seed says it differently.

**Gaps in what it can assert**
- **Roles that should not see a figure:** the office, cases and rules permission files give every role access. So "a role that should not see it gets 403" is only checked as "no session gets 401 or 403". If the universe wants a role to be blocked, the universe and the permissions disagree.
- **The 8 Oct fixing (1.3388):** it is in the expected output but not asserted, because no route returns it.

**Re-running it once D.md lands**
1. Build a temp root under `.sh-tmp/verify/uc4/data`. Seed it with `seed_evergreen.py --data-root ROOT --reset`, then `seed_10uc.py --data-root ROOT --reset`, then `seed_v3_demo.py --data-root ROOT`.
2. Serve it with `serve_test.py --port 8653 --data-root ROOT`.
3. Run `python tools/verify_10uc/uc4.py --base http://127.0.0.1:8653 --creds ROOT/_control/seed_credentials.txt --out DIR`.

The seed writes the creds file at `ROOT/_control/seed_credentials.txt`.

---

File: `<repo>\tools\verify_10uc\uc6.py`

It compiles and the universe lookups load, but I have not run it against a server. `docs/plan/v4-landings/D.md` does not exist yet (only K1–K8 are there), so per your instruction I did no seed, serve or checker run. I touched nothing else, and the creds file and port 8400 were never opened.

**What the checker does**
- It logs in through `/api/auth/login` as Raj Patel (approver), then calls `/api/v1/office/liquidity?as_of=2026-10-09`, `/api/v1/cases?status=active&exception_type=capital_call`, `/api/v1/managers/inbox` and `/api/v1/managers/{id}`.
- It reads every figure from `docs/test/10uc_universe.json` and compares as Decimal.
- It writes `DIR/uc6/P21.json` to `P24.json` and `result.md`, and exits 1 if any fact fails.

**Facts (all unrun)**

| Fact | What it asserts |
|---|---|
| P21 | Entity B 30-day bucket holds the Fund C call (450,000, due 20 Oct, confirmed) and the Fund E call (600,000, due 30 Oct, noticed, flagged unconfirmed). Total calls are 1,050,000. The Finance case "Fund the capital call" is visible to the approver. |
| P22 | Available cash 880,400. After the confirmed call 430,400. After both calls -169,600, which should also equal the bucket's `cash_after_calls`. Exactly one `capital_call` case, tied to Fund C's instrument and none for Fund E. |
| P23 | Fund D call 250,000 due 4 Dec, confirmed, in Entity B's 60-day bucket. Fund A distribution 320,000 due 16 Nov, noticed, in Evergreen Holdings' 60-day bucket. |
| P24 | Committed, called and uncalled for funds A–E across the manager profiles, with called never above committed. Uncalled per entity on the Office view: Evergreen Holdings 4,550,000, Entity B 8,900,000. |

**Who should not see it:** Grace Ong (company_admin). The seed puts her in no access group, so the liquidity route should show no entity, cases should show no `capital_call` case, and the manager profile should show no commitment rows. A 401, 403 or 404 also counts as a pass.

**Likely failures once the data exists**

These are guesses from reading the code, not evidence.
- **P22 case:** the universe wants a case for the Fund C call, but the K4 notes say the case is opened by `alert_if_due`, which runs when a notice is confirmed. A raw warehouse load that doesn't call it would leave no case, so the seed (`seed_10uc`) would be at fault, not the product.
- **P24 manager profile:** `_commitments` in `k5_managers.py` returns "not available" if the `commitments` table is missing. That would be a seed or loader gap.
- **P24 uncalled figures:** the product derives called from confirmed, non-superseded calls. If `seed_10uc` loads `called_before_2025_08` plus movements differently from the universe's `called_to_date`, the product and the universe would disagree, and I would call that a seed issue.
- **Grace's access:** if Grace turns out to see Entity B, either the seed's access groups are wrong or E1d is not failing closed. Her access depends on the seed's group membership, not on the route's permissions, which allow every role.

To run it once D.md lands: seed evergreen, then `seed_10uc`, then `seed_v3_demo` into `.sh-tmp/verify/uc6/data`. Serve with `serve_test.py --port 8655 --data-root ROOT`, then run the checker with `--creds ROOT/_control/seed_credentials.txt`.

---

File: `<repo>\tools\verify_10uc\uc3.py`

I did not run the checker against a live server, because `docs/plan/v4-landings/D.md` does not exist yet (only K1 to K8 are there). I checked it with `py_compile`, which passed, and ran its date helpers on the universe dates. I ran no seeds and started no server. Port 8400 and `data/` were not touched.

Usage: `python tools/verify_10uc/uc3.py --base http://127.0.0.1:PORT --creds PATH --out DIR`. It reads the passwords from the creds file and does not print or write them. It logs in as Mei Chen (analyst) for every fact. Sofia Reyes (participant) is used only to check that she gets 403 on the follow-up draft.

| Fact | Status |
|---|---|
| P09 | unrun |
| P10 | unrun |
| P11 | unrun |
| P12 | unrun |
| P13 | unrun |

What each fact checks, all through `/api/v1/managers/inbox`, `/managers/{id}`, `/managers/{id}/followup` and `/evidence/asof` and `/evidence/chain`:
- **P09:** the September due date, first received date, state and last value per fund, with the status word (estimated, unverified, official or revised). C and D must show `not_due`.
- **P10:** H2 Aug, E Jun and D Mar are checked by running the inbox at a date in the following month. It checks due date, received date, `received_late` and business days late.
- **P11:** D 30 Jun must appear in `earlier_missing` with the right due date and 63 business days overdue. It also checks the follow-up draft (see the next section), the participant 403, and that an unauthenticated request gets 401 or 403.
- **P12:** old then new value for A (Sep), C (Jun) and H1 (Jul), and the change between them, read from the evidence chain. It also checks the amended statement on the manager profile timeline, and A's `revised_count`, last value and "revised" status in the inbox.
- **P13:** one inbox row per fund under the canonical names, no alias shown as its own row, Kestrel Ridge shows two funds, and H1's July final and amended statements sit on the same fund, with the second name on the amended title. It also checks that H1's identifiers include code 4481 and both names.

Failures I expect, and whose fault each would be:
1. **P10 and P11, days late.** `k5_managers.py` computes `days_late` as calendar days (`(as_of - due).days` and `(first - due).days`), but the universe says business days. D June would come out as 87 instead of 63, and H2 August as 8 instead of 6. This is a **product** bug. The universe is self-consistent: I checked that 63 is the weekday count from 14 Jul to 9 Oct.
2. **P11, follow-up draft.** The draft opens "Dear {manager name} team", and the product has no contact-name field. "Addressed to Hana Sato" would therefore fail. This is a **product** gap, since the manager contact exists in the universe. The seed would be wrong only if `seed_10uc.py` is meant to store contacts and does not.
3. **P12, A.** If `seed_10uc.py` is run with `--hold-amended-a`, or the amended Fund A statement was never loaded (the universe says the demo drops it in later), A's revised checks fail. That is a **seed or run-mode** matter, not a product bug. To check P12 fully, run the seed without the hold flag.
4. **P13 and P12, tables.** These read `instrument_identifiers` and `valuation_observations` through the evidence routes. If those tables are not exposed there, the check fails with a plain 400. That would be a **checker or route** gap, not a data problem, so look at the actual response before blaming the seed.

Everything else is read from `docs/test/10uc_universe.json`, with no second copy of any figure. Once D.md appears, run the sequence from your brief: `seed_evergreen.py --reset`, `seed_10uc.py --reset`, `seed_v3_demo.py` (check each script's flags first), then `serve_test.py --port 8652`, then the checker, then stop the server.

---

**Unrun.** `docs/plan/v4-landings/D.md` does not exist yet. The folder holds only K1.md to K8.md, so I did not seed or serve anything. The checker is finished and passes `py_compile` with the venv Python.

**File:** `<repo>\tools\verify_10uc\uc5.py`

Run it with `--base`, `--creds` and `--out`. An optional `--as-of` defaults to the universe `meta.as_of` (2026-10-09). Seed order once D lands:
- `seed_evergreen.py --data-root ROOT --reset`
- `seed_10uc.py --data-root ROOT --reset`
- `seed_v3_demo.py --data-root ROOT`
- `serve_test.py --port 8654 --data-root ROOT`

The creds file is `ROOT/_control/seed_credentials.txt`.

**Facts (all unrun):**
- **P17 (HVS single-name breach, real):** unrun. The checker:
  - runs `POST /api/v1/recon/limits/run` as Mei Chen;
  - lists `GET /api/v1/cases?exception_type=limit_breach` as Mei Chen and Sofia Reyes;
  - checks that the run's `causes` entry says "real breach";
  - checks that the case description says "It is 5.7%" and "Cause: real breach.";
  - checks that the impact amount is exactly item_value minus 5% of the total, which is 308,000.00;
  - checks that Raj Patel and Daniel Foo get 403 on the run (POST). Sofia Reyes also gets 403 on the POST but 200 on `GET /api/v1/recon/runs`.
- **P18 (Cedarpoint C+D, stale data):** unrun. Same checks, with 56.5%, "stale data" and an impact of 343,750.00. The EG-B-OPS total is taken from the universe `nav_bridge_30_sep`.
- **P19 (PRC29 has no class):** unrun. The checker:
  - reads `GET /api/v1/office/holdings?as_of=2026-09-30` as Sofia and Mei;
  - expects the PRC29 line to have value 1,122,000 and status containing "Needs a class";
  - expects no case naming Pacific Rim and no "classification" cause in the run;
  - expects Sofia to be able to open the Limits run.
- **P20 (limits within range):** unrun. The checker expects:
  - no case titled listed_equity or hedge_fund;
  - exactly 2 breaks in the run;
  - the universe's 80.61% and 54.95% to match value divided by total and sit inside their ranges.

**Likely failures to expect:**
1. **The percentage in the product vs the universe.**
   - The case description rounds to 1 decimal place (`{share:,.1f}`). The exact share is 5.7476%, which shows as "5.7%". The universe says 5.75% (2 dp) and `e3_recon.py` never returns a 2 dp share.
   - I therefore assert 5.7%/56.5% at 1 dp plus the exact impact amount, and check separately that the universe's 2 dp figure equals value divided by total. The 2 dp figures in P17, P18 and P20 cannot be read from any API.
   - This is a product gap. If the 2 dp share must be visible, the run record or case needs an `exposure_pct` field. The universe is correct. I confirmed 5.7476 → 5.75, 56.5027 → 56.50, 80.608 → 80.61 and 54.945 → 54.95.
2. **Participant access to Limits.** Settled: GET runs is open to every company role; POST run is company_admin and analyst only.
   - The universe lists "participant" as the role for P19 and P20 (Limits screen). The participant reads the last run (`GET /api/v1/recon/runs`: the P19 question and the P20 results lines) and gets 403 on `POST /api/v1/recon/limits/run`.
   - The checker expects 200 on GET runs and 403 on the POST.
3. **"Needs a class" for PRC29.** P19 now reads it from `questions` in the Limits run record, not from `causes`.
   - There is no hit for the string "Needs a class" in any code, only in the universe docs. The K2 `_status()` in `k4_office.py` only yields stale/official/revised/estimated/unverified, so the P19 status check will probably fail.
   - That is a product gap: PRC29 needs a classification status. The seed is a lesser suspect (PRC29's `asset_class` is None in the universe).
4. **As-of date.**
   - The universe's limit table is keyed "30 Sep", but the P18 text cites 192 days, which is as of 9 Oct. I default to 9 Oct. Pass `--as-of 2026-09-30` if that is the intended date.
   - The case title contains the date, so a case already opened for another day will not be re-opened.

---

I wrote the checker at `<repo>\tools\verify_10uc\uc1.py`. It compiles but has not been run. `docs/plan/v4-landings/D.md` doesn't exist yet (only K1 to K8), so I did no seeding or server start. I touched nothing else.

**What it does**
- Run it with `--base`, `--creds` and `--out`. It logs in as Daniel Foo (sponsor), Mei Chen (analyst) and Sofia Reyes (participant), reading passwords from the creds file.
- It writes `uc1/P01.json` to `P07.json` and `result.md`, and exits 1 on any failed fact.
- All figures come from `10uc_universe.json` and are compared as Decimal.
- It reads from `/api/v1/office/{issued,nav-bridge,holdings}`, `/api/v1/brief/{rvid}` plus its `/explain`, `/api/v1/pulse2/items` and `/api/v1/rules`.

**Facts**

| Fact | Status |
|---|---|
| P01 September report as issued | unrun |
| P02 Fund A amended statement | unrun |
| P03 NAV bridge EG-GROWTH | unrun |
| P04 NAV bridge EG-B-OPS | unrun |
| P05 NAV bridge EG-FUNDS | unrun |
| P06 Liquid book Aug to Sep | unrun |
| P07 Holdings status words | unrun |

**Failures I expect from reading the code** (the first needs a product or universe decision):
- **P07, "Needs a class" for PRC29:** the string appears nowhere in `sh_platform`, `ui/src` or `tools`, and the holdings response has no asset-class field. The `PRC29 shows 'Needs a class'` check will fail. Either the product or the universe is wrong. The universe ties this wording to P19 (limits), so I think the P07 wording is misplaced. The checker also asserts PRC29's value of 1,122,000.
- **P06, "Why did this move":** the sponsor reads `GET /api/v1/office/why-moved?start=2026-08-31&end=2026-09-30&book=liquid` and expects 39,552,000 to 41,200,000, +1,648,000, 4.1667%, largest Northwind Logistics +132,000, and a trades list that names FXF-2026-001. The per-security check from `/office/holdings` is kept.

**Gaps in what the checker can assert**
- **P01:** the issued view exposes no as-issued status word for Fund A or the Total, so "estimated" is not asserted. B and Liquid book are checked as official.
- **P07, Fund E value:** the shown value is a soft check only, because the universe does not say whether 9,950,000 or 9,600,000 should appear.
- **Negative access:** the seed gives every person except the data team full access to all entities, and the data team read access, so no seeded role is refused office data. The negative checks are therefore signed-out requests (expect 401 or 403 with no figures) and participant on `/api/v1/rules` (expect 403, since the rules route allows only company_admin, sponsor and analyst).

**Next:** when D.md lands, run seed_evergreen, seed_10uc and seed_v3_demo into `.sh-tmp/verify/uc1/data`, serve with `serve_test.py --port 8650`, then run the checker. I'll say whether any failure is the product, the seed or the universe once I have real responses.

---

File: `<repo>\tools\verify_10uc\uc7.py`

It compiles with `py_compile` but is unrun. `docs/plan/v4-landings/D.md` does not exist (the folder only has K1 to K8). So no seed, no server, and no run against port 8656.

**What it does**
- Reads the universe JSON for all figures and logs in through `/api/auth/login` using the passwords in the creds file. It prints and writes no passwords.
- Writes `DIR/uc7/P25.json`, `P26.json`, `P27.json` and `result.md`, and exits 1 if any fact fails.
- Routes used: `/api/v1/managers/{slug}`, `/changes`, `/inbox?as_of=`, and `/api/v1/evidence/asof` (valuation history).
- Each fact also has negative checks. An anonymous request must be refused, and each role the universe does not name (approver, participant; analyst for P26) must get 403/404 or a body without the fact.

**Fact status**
- P25 newsletter team change: unrun
- P26 what changed since 12 Jun: unrun
- P27 Cedarpoint profile: unrun

**Likely failures, from reading the code only**
These are my predictions, not results:
1. **P26 "6 business days late".** `k5_managers._fund_row` computes `days_late` as calendar days (received minus due). That gives 8 for 22 Sep against 14 Sep, while the universe and the signed rule say 6 business days. Product.
2. **P26 "7,050,000 to 7,012,500".** `changes()` only says "A revised statement … arrived" and gives no figures. The checker also reads the as-known-before and as-known-now NAV from `evidence/asof`, which should pass. Product gap, or the universe expects more than the answer carries.
3. **P27 DDQ terms ("45 days", "auditor change in Q2 2026").** No route returns DDQ text on the manager profile. The only text source is `changes().passages`, which searches documents newer than the cut. The checker asks for `since=2026-01-01` so the DDQ (dated 5 Mar) is included. Product, unless the search happens to return it.
4. **P27 "stale".** The profile gives Fund D's last valuation date (31 Mar 2026) but never says "stale". Product wording, or the universe is over-specified.
5. **P27 called and uncalled amounts.** `k6_liquidity` counts confirmed calls only. The universe has 450,000 (C) and 250,000 (D) noticed but unconfirmed, so called and uncalled may differ. Product or seed.
6. **Role negatives.** The manager GET routes allow every consumer role (approver, participant, and so on), but the universe names only "sponsor, analyst" (P26 only "sponsor"). All of Daniel, Mei, Raj and Sofia are in the "Investment office" access group, and Anita and Leo are in the "Data team" group; every group has access to all three entities. So Raj and Sofia will probably see the facts. Product (permissions yaml) or universe (role list too narrow).

The checker also expects `seed_10uc` to have loaded the library files with their own `at` dates, the meeting notes, and Cedarpoint's open question. If a check fails because of that, the blame is the seed. I left `seed_10uc.py` alone.