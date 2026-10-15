# Journey writers: missing or confusing screens found while reading the code

Both scripts are written and compile (`py_compile` passes), but they are unrun. `docs/plan/v4-landings/D.md` does not exist, and `ui/dist/index.html` (15:57) is older than `ui/src/v1/k4` (16:36). I did not run vite or start any server.

**Files**
- `<repo>\tests\e2e_10uc\uc9a_1.py`
- `<repo>\tests\e2e_10uc\uc9a_2.py`

Both take `--base URL --creds PATH --out DIR` and use a 1440x900 Chromium viewport. They log in as Daniel Foo, with the email read from `10uc_universe.json` and the password from the creds file, never printed. They submit the login form with `requestSubmit()`. They read the P32 figures from `10uc_universe.json` under `process`.

After every step each script takes a full-page screenshot to `DIR/uc9a_N/NN-<step>.png`. It then fails the step if the page text shows `undefined`, `[object`, a traceback, "Internal Server Error", `NaN` or a raw id such as `intent-<hex>`. It writes `DIR/uc9a_N/result.md` and exits 1 on any failure.

**Charter 1: sponsor sees the signed swim lane (P32)**
1. Login: the sponsor signs in and leaves `/login`.
2. Intent list: `/centre/intent` is opened and the "Monthly investment report in USD and SGD" link is clicked if listed. The URL must become `/centre/intent/<id>` and that title must show as a heading.
3. Signed state: a "Signed" pill and "Version" text are visible.
4. Swim lane: the group labelled "Process map" holds all six `Step n: <name>` buttons, plus lane labels Mei Chen, Raj Patel and Daniel Foo.
5. Systems: File drop, Excel, Email and Report pack are shown on the cards.
6. Hand-overs: "To step 2" through "To step 6" appear on the cards.
7. Manual flags: the "Manual" pill appears on exactly steps 1-4, and the "Manual step" legend is visible.
8. Map locked: the "That's right" button is disabled once the intent is signed.

**Charter 2: Download the SOP (P32)**
1. Login and open the intent, as in charter 1.
2. Preview: the "Download the SOP" link is visible. Clicking "Preview the SOP" opens the "SOP preview" panel with a heading matching the project title.
3. Roles: the Purpose and Roles lines name Mei Chen, Raj Patel and Daniel Foo.
4. Six steps: names are in order. Each step shows Who, System, Control (from the universe) and "If it goes wrong" (the exception, from the universe), and its Input and Output are non-empty.
5. Manual flags: "Manual: could be automated" appears on steps 1-4 only.
6. Hand-overs: "Hand over to step 2" through "Hand over to step 6" are listed.
7. Download: clicking the link must save a `.docx` or `.md` file. The script saves it into `DIR/uc9a_2/`, checks it is over 1000 bytes, and unzips a `.docx` to read the text. All six step names must be in the file and none of the "undefined" strings.
8. Hide: "Hide the SOP" closes the panel.

**Screens I found missing or confusing**
- `ui/src/v1/i6/Swimlane.tsx:23` decides the "Manual" pill with the regex `MANUAL` on step name plus "does" text. It ignores the `manual` field that the SOP panel uses (`SopPanel.tsx:30`). If a step's "does" text lacks "excel", "manual" or "by hand", the map and the SOP can disagree. For example, "Collect the exports" and "Convert to SGD" may not match. Step 7 of charter 1 will catch this.
- `ui/src/v1/i6/SopPanel.tsx:20` shows "Download the SOP" only when the intent is signed, and the signed block is inside the chat log (`ConversationPage.tsx:~290`). It is hidden if the Workbench chat pane is collapsed or small.
- `ui/src/v1/p3/IntentWelcome.tsx:65` renders the conversation directly when an open intent exists, with no recent list. The scripts then rely on that open intent being the month-end one, and fail at the title assertion if not.
- The swim lane is not titled "Process map" on screen. `Swimlane.tsx:18` only gives the group an aria label. The document tab name comes from `ConversationPage.tsx:~215` and the Workbench, so I rely on the aria label.
- The SOP panel never shows the file type. The download is a plain `<a download>`, so the screen does not tell the user whether they get .docx or .md. P32 says either.

---

Both scripts are written and pass `python -m py_compile`. I did not run them. `docs/plan/v4-landings/D.md` doesn't exist (the folder only has K1.md to K8.md). `ui/dist/index.html` is also older than `ui/src/v1/k4` (15:57 against 16:36). I started no test copy and no server.

**Files** (`tests/e2e_10uc/`, nothing else touched):
- `<repo>\tests\e2e_10uc\uc3b_1.py`
- `<repo>\tests\e2e_10uc\uc3b_2.py`

Both take `--base --creds --out`, run Chromium at 1440x900 and log in as Mei Chen (analyst) through the form submit trick. The password is never printed or saved. They screenshot every step to `DIR/uc3b_N/NN-step.png`, write `result.md`, and exit 1 on any failure. A failed step doesn't stop the run, so one failure doesn't hide the rest. They fail on raw UUIDs, "undefined", "NaN", "Traceback" and "Internal Server Error" on any screen. All figures and names come from `docs/test/10uc_universe.json`.

**Charter 1, P12 revised statements (`uc3b_1.py`)**
1. Sign in.
2. Open `/centre/action/managers`. Assert every manager name and the word "revised" are on the page.
3. The Evergreen Growth I row shows "Revised once" and last value "USD 10,180,000" (the amended figure, not the 10,000,000 estimate).
4. The Northgate Partners card says "1 revised".
5. For each of A, C and H1:
   - Open Consume > Managers and click the manager.
   - In the "Statements" region, find the link "<fund>, valued <date>" with "replaces an earlier statement". It must show "received <date>" (2 Oct is not involved; the dates are 7 Oct for A, 18 Aug for C, 20 Aug for H1) and "official", and must not say "replaced by a later one".
   - Click through to the evidence page. It must show both the original and amended figures: 10,000,000 and 10,180,000 for A, 8,420,000 and 8,275,000 for C, 7,050,000 and 7,012,500 for H1.
6. Run result: unrun.

**Charter 2, P13 same fund under two names (`uc3b_2.py`)**
1. Sign in.
2. On Action > Managers, neither "KR Macro Fund Ltd - Class B USD" nor any "Fund B - ..." string appears.
3. The Kestrel Ridge Advisors card has exactly one row for Kestrel Ridge Macro Fund, and one for the Equity Long/Short fund.
4. The Bluewater Capital card has exactly one row for Evergreen Income II.
5. On the Kestrel manager page, the Funds region lists Kestrel Ridge Macro Fund once and never the alias.
6. The July statements timeline link is "Kestrel Ridge Macro Fund, valued 31 Jul 2026", with no alias in the region.
7. The evidence page reads `"KR Macro Fund Ltd - Class B USD" to Kestrel Ridge Macro Fund`, matched or proposed, and not "not matched to any fund yet".
8. Settings has an identifiers link. After clicking it, Kestrel Ridge Macro Fund, the alias and administrator code 4481 are on screen.
9. Run result: unrun.

**Missing or confusing screens found while reading the code**
- **No identifiers screen.** There is no "Settings > identifiers" screen, and the P13 charter and the universe assume one. `ui/src/v1/s1/SettingsPage.tsx:61-70` lists only People and access, Rules, Sources and data model, Templates and skills, Signed register, Agent runs and cost, Testing or Real use, and What the agents remember about you. `grep -i identifier` in `ui/src` only hits `ui/src/v1/e2/EvidencePage.tsx:64` ("Approve this match"). The last step of `uc3b_2.py` will therefore fail with "Settings has no identifiers section" until one is built. The fix is either an identifiers section or a change to the charter wording.
- **Inbox only counts the latest period.** `sh_platform/v1/k5_managers.py:143-145,162` filters to last month's period, so "Revised once" and the "N revised" count only reflect September. The C (June) and H1 (July) revisions never show in the Action inbox. They appear only in the Consume timeline, so the P12 "Action > Managers > revised" location is only true for fund A. `uc3b_1.py` asserts the Action side for A and Northgate's "1 revised", and C and H1 on the Consume timeline.
- **Timeline shows no figures.** In `ui/src/v1/k5/ManagerPage.tsx:~100`, the "Statements and revisions" list shows the fund, valuation date, received date and status, with no values or deltas. The +180,000, -145,000 and -37,500 changes are only visible by clicking through to `EvidencePage`, whose "Original" and "Amended" columns are hard to scan.
- **Alias hidden from managers list.** The `ManagerList` at `ui/src/v1/k5/ManagerPage.tsx:20-32` doesn't show fund names, so the aliasing can only be checked on the inbox and profile pages.

---

Both scripts are written and pass `python -m py_compile`. Neither has been run. `docs/plan/v4-landings/D.md` doesn't exist (only K1–K8), and `ui/dist/index.html` has the 9 Oct 15:57 timestamp, so the gate failed and I started no test copy or server.

**Files**
- `<repo>\tests\e2e_10uc\uc2a_1.py`
- `<repo>\tests\e2e_10uc\uc2a_2.py`

Both take `--base --creds --out`, use a 1440x900 viewport, read figures from `docs/test/10uc_universe.json`, and log in through the form with `requestSubmit()`. Each step is screenshotted to `OUT/uc2a_N/NN-step.png`. Each step also fails on a raw uuid, `undefined`, `NaN`, `Traceback`, `Error:` or `null` on screen. `result.md` is written to the same folder, and the exit code is 1 on any failure.

**Charter 1: `uc2a_1.py`, Mei Chen (analyst)**
1. Open `/centre/action/reconciliations`. The "Cash by entity" card and a Run now button are visible.
2. Fill "Check as at" with 2026-10-08, because the default is the browser's today.
3. Click Run now. The card says "as at 2026-10-08" and there is no alert.
4. The card shows "1 break(s) open" and "3 compared".
5. The tolerance reads "up to 5,000 USD" (from `cash_tolerance` in the universe). The card must not show "signed rule …".
6. The card has no line for Holdings or the Trust, and has a "Where is this from?" button.
7. Cases has exactly one row titled "Cash differs · Entity B · 2026-10-08" sized "USD 12,400", and none for the Trust.
8. The case page heading has USD 12,400. The "What was compared" section has 880,400, 868,000 and 12,400.

**Charter 2: `uc2a_2.py`, Mei Chen, then Raj Patel (approver)**
- If the case isn't there yet, the script runs the cash check first.
1. Cases list shows the Entity B break with USD 12,400.
2. Open the case. The title, size, "What was compared" and the "Ask the agent to explain" button are shown.
3. Click "Take case" if shown. State reads Assigned or Being investigated, and "Submit for check" appears.
4. Click "Ask the agent to explain" (waits up to 90s). The "Proposed by the investigation agent" section appears with text.
5. Click "Submit for check" and type the note into "Explanation to send for check". The note is built from universe figures: 880,400, 868,000, 12,400 and the 5,000 tolerance.
6. Click Confirm. State reads "Waiting for a check", "Submit for check" is gone, History contains 12,400, and there is no alert.
7. As Raj, open Today (`/centre/action`). The card headlined with the case title is visible. The script steps through the "Viewing as" roles if the default view doesn't show it.
8. Raj opens the card's link. The case shows "Waiting for a check", Approve, Send back, and the analyst's note in History. The script does not press Approve.

I treat the submit explanation as the "note", because the screen has no separate note field. The charter 2 note step and the History check depend on that.

**Missing or confusing screens**
- **No note field:** The case page has no way to add a note. The API has `POST /api/v1/cases/{id}/note` (`sh_platform/v1/e4a_routes.py:~79`), but `ui/src/v1/e4/CasePage.tsx` (buttons at lines 18–19) never calls it.
- **Approver never gets a "Your approval" card:** The UI submit sends no `checker` (`ui/src/v1/e4/api.ts` FIELD map, `ui/src/v1/e4/CasePage.tsx:25`). `C.submit` only creates the approval row when a checker is named (`sh_platform/v1/e4_cases.py:262`). Raj therefore sees only the ordinary break card, and only if the Finance/Operations role view includes it. Charter 2 step 7 may fail for that reason.
- **Take case on a waiting case:** Today shows "Take case" on every card that has a `case_id` (`ui/src/v1/e5/TodayPage.tsx:52`), including a case already waiting for a check, where the server forbids taking it.
- **Plural wording:** `ui/src/v1/a5/ReconPage.tsx:~38` renders "1 breaks open" (no singular form). Charter 1 step 4 accepts either spelling.
- **Raw id possible:** When the server sends no tolerance words, the card shows "signed rule {id}" (`ui/src/v1/a5/ReconPage.tsx:~42`). Charter 1 step 5 fails if that happens.
- **Default date:** "Check as at" defaults to the browser's today (`ui/src/v1/a5/ReconPage.tsx:17`). The planted cash data is for 8 Oct, so a plain Run now on any other day misses P08.
- **Case page link:** The "All cases" breadcrumb points at the old `/centre/desk` (`ui/src/v1/e4/CasePage.tsx:35`). It works only because `ui/src/v1/a5/ActionCentre.tsx` rewrites it.

Charter 2 changes state: it takes the case and submits it. Run it on a fresh test copy, and rerunning on the same data will fail at the Take/Submit steps.

---

Files: `<repo>\tests\e2e_10uc\uc8a_1.py` and `uc8a_2.py`.

**Run result: unrun.** Both compile (`py_compile` passes). I did not run them because `docs/plan/v4-landings/D.md` doesn't exist; that folder holds only K1 to K8. `ui/dist/index.html` is dated Oct 9 15:57, but the D.md gate failed first, so I didn't check it against `ui/src/v1/k4`.

Both scripts are standalone (`--base --creds --out`, Chromium, 1440x900). They log in as Mei Chen (analyst) from the creds file, never print the password, and submit with `requestSubmit()`. Each step is screenshotted to `DIR/uc8a_N/NN-<step>.png`. `result.md` is written there and the script exits 1 on any failure. Every step also checks the screen for "undefined", `[object`, "Traceback", NaN, null, UUIDs and error copy. All figures come from `10uc_universe.json`.

**Steps shared by both charters:**
1. Sign-in page shows Email, Password and a Sign in button.
2. After submit, the sign-in page goes away.
3. `/centre/action` shows the tabs Today, Cases, Reconciliations and Managers.
4. The Reconciliations tab lists the card "Trades against the administrator".
5. Set "Check as at" to 2026-10-09 and press Run now on that card. Assert "N breaks open", "as at 2026-10-09", the rule words "must match by trade id" and "5,000 USD".
6. The Cases tab shows a table.

**Charter 1 (P28, P29):**
- **P28:** Exactly one row for T-20261002-003. It must read "Trade differs", Northwind Logistics, and 75,870. The case page has a "What was compared" region with "Trading export 505,800.00", "administrator 429,930.00" and "difference of 75,870.00". The administrator figure is derived as 10,200 × 42.15.
- **P29:** One row for T-20261006-005. It must read "Trade not matched", Harborview Semiconductor, and 592,000. The case page says "This trade is in the trading export", names the portfolio, and says "no matching trade at the administrator".

**Charter 2 (P30, P31):**
- **P30:** One row for FXF-2026-002 reading "Trade differs", with a size of SGD 8,100 or 6,050.19. The case page shows 8,100.00 or 6,050.19 in "What was compared".
- **P31:** No row for FXF-2026-001, T-20261001-001, T-20261002-002 or T-20261007-006.

**Screens that are missing or confusing:**
- `ui/src/v1/a5/ReconPage.tsx:13-15`: the trades check is declared in a local `MORE` list rather than the shared `CHECKS`. If someone adds it to `CHECKS` later, the card moves but the heading text stays the same, so the scripts are fine.
- `ui/src/v1/e4/CasePage.tsx:46`: the "All cases" crumb links to `/centre/desk`. It only stays inside Action because `Stay` in `ActionCentre.tsx:21-30` rewrites it. The scripts rely on that.
- `ui/src/v1/e4/CasesPage.tsx:21`: the page title is "Action Desk" under the "Action" frame heading, so there are two headings for one screen. I locate the frame heading with `exact=True`.
- `ui/src/v1/e4/CasesPage.tsx:7`: `money()` drops the decimals, so the list shows "USD 75,870" but the case text shows "75,870.00". The scripts assert each form where it appears.
- `sh_platform/v1/e3_recon.py:306`: case titles include the raw external trade id ("... · T-20261002-003"). That is the only place a trade id shows, and my raw-id check allows it. The FX case title also uses the instrument name, which may be generic for forwards. I only assert the FXF id.
- `ui/src/v1/a5/ReconPage.tsx:35`: the "N breaks open" count comes from the whole run. A fresh seed should show 3 for trades, and I only assert that the text appears.
- Two risks for the first real run. The FX case's currency (SGD or USD) depends on the seed, and the scripts accept either. The Cases table lists every open case, so the row filters rely on the trade id appearing in the title.

---

Written: `<repo>\docs\test\UX-REVIEW-1.md` (25 suggestions, top ten first, plus a "keep it" list). No code changed.

Top ten:

| Id | Screen | Where | Problem | Change | Sev | Owner |
|---|---|---|---|---|---|---|
| UX-01 | Consume | `ui/src/v1/cxui/ProjectList.tsx:30-53`, `k4/routes.tsx:7-8`, `k5/routes.tsx:8` | Office view, CIO Brief and Managers research are reachable only by typed URL; nothing links to them. The CIO's most valuable screens are unreachable. | Give Consume a tab row like Action: Office view · Managers · Dashboards. Land sponsor/approver on Office view, analyst on Dashboards. | 1 | A6, A7, A8 |
| UX-02 | Consume/Build project pickers | `ProjectList.tsx:31,37,43`, `b6/ProjectsPage.tsx:21`, `s1/ProjectPicker.tsx:48` | Three pickers, three wordings, rows lead with codes ("EV-0003 · … · Build", "Dashboards of EV-0003"). | Use the one shared `s1/ProjectPicker` in both centres. Label "Find a project", placeholder "Monthly report", title first and number muted, heading "Dashboards for Monthly report". | 1 | A6, A5 |
| UX-03 | Intent | `i6/ConversationPage.tsx:265,632-635,660` | Main action renames itself: "Hand to the architect" → "Send to Build" with "puts a card in front of the head of data". First-visit title "Talk to North" tells a newcomer nothing. | Ready → "Sign the intent of work"; signed → "Send to Build" with "The head of data will plan the build." First visit: title "What do you need?", subline "Describe the report, check or process you want in your own words. North, the industry expert, drafts it beside you." | 1 | A2 |
| UX-04 | Action · Today | `e5/TodayPage.tsx:36`, `a5/ActionCentre.tsx:74` | Two stacked page headers with near-identical sublines; cards start a screen down on a phone. | Embedded tab pages render without their own `PageFrame` title. One title per screen in every centre. | 2 | A3 |
| UX-05 | Build · project | `b6/BuildPage.tsx:74-80,101-105` | Subline does not say whether *I* must act; the only button is disabled with no reason; document "3 Tables" uses engineer words. | Role-based subline ("Check Span's plan, then approve it." / "The data team is building this. You will be told when it is live."); reason under disabled button ("Only the data team can ask for a plan."); rename to "Tables", SQL under collapsed "How it is calculated". | 2 | A5 |
| UX-06 | Settings | `s1/SettingsPage.tsx:72,54` | Fixed 180–240px side column, no phone rule: content column ~130px at 390px, six-column table breaks the page. 50-word intro about seats. | Stack nav above content under 720px (same breakpoint as `shell/barStyle.ts:19`). Intro: "Who can open which centre. The administrator sees everything." | 2 | A1 |
| UX-07 | Office view (and CIO Brief) | `k4/OfficePage.tsx:62-78,102-107,168-173`, `e5/BriefPage.tsx:44-51` | Five-column tables with a full "Where is this from?" button per row overflow phones and shout louder than the figures; USD/SGD chips unlabelled. | Holding name becomes the trigger, drop the button column, wrap tables in `overflow-x: auto`, label chips "Show in". | 2 | A7 |
| UX-08 | Shell top bar | `shell/copy.ts:15-21`, `CentreShell.tsx:70` | All-caps single words (INTENT, CONSUME…) and a raw role chip ("Company admin", "Analyst") that does not match real jobs. | Sentence case 14px labels with a one-line `title` each ("Say what you need", "What needs you today", "Build the data", "Reports and dashboards", "How it all connects"); hide the role chip. | 2 | A1 |
| UX-09 | Reconciliations (and Cases) | `a5/ReconPage.tsx:35,48-51`, `a5/CaseView.tsx:14` | "Signed tolerance", "breaks open", "signed rule version not recorded" is ops jargon plus a system note. | Intro "These checks compare two records of the same money. Every difference beyond the agreed allowance becomes a case."; pill "3 differences to look at" / "Everything matches"; "Allowance: {rule_words}" or "Allowance: not stated"; "The two records compared". | 2 | A4 |
| UX-10 | Intent process map, Map process tab | `i6/Swimlane.tsx:18,31` | Grid forces 110 + steps×156 px (eight steps = 1,360px): silent sideways scroll on laptop, 1.5 steps on a phone, a dozen tab stops. | Under 760px render the numbered list (lane, name, Manual pill); above it keep the swim lane with "Scroll sideways to see all {n} steps." | 2 | A2, A9 |

---

Both scripts are written and pass `py_compile`. They are unrun, because `docs/plan/v4-landings/D.md` does not exist (only K1 to K8 are there). The bundle also isn't confirmed rebuilt. I didn't start any servers.

**Files**
- `<repo>\tests\e2e_10uc\uc7a_1.py`
- `<repo>\tests\e2e_10uc\uc7a_2.py`

**How both scripts work**
- Both log in as the sponsor, Daniel Foo, through the login page. They fill Email and Password, then submit with `requestSubmit`.
- Passwords come from the creds file and are never printed or saved. The expected facts are read from `docs/test/10uc_universe.json`.
- They use a 1440x900 viewport and write `DIR/uc7a_N/NN-<step>.png` and `result.md`. They exit 1 on any failed step.
- Every step also checks the page for raw ids, "undefined", "null", NaN and error text.
- Dates are normalised first, because en-GB date formatting in Chromium can print "Sept".

**Charter 1, `uc7a_1.py` (P25)**
1. Open `/centre/consume/managers`. Assert the heading "Managers" and that Kestrel Ridge Advisors is listed.
2. Click the Kestrel Ridge link and assert:
   - the title and the "Kestrel Ridge Macro Fund" line;
   - the section "What changed since the last meeting?" and one "Show what changed" button.
3. Click "Show what changed" with no date and assert:
   - Thomas Lindqvist and Priya Nair are named;
   - "28 Sep 2026" appears;
   - a `.ds-chip` names the newsletter and cites "lines N to N";
   - the heading "From the documents" is present.
4. Verdict check: none of "good news", "bad news", "worrying", "concerning", "positive", "negative", "red flag", "recommend" appears, once the standing "does not say whether a manager is doing well or badly" sentence is removed.
- Soft checks (notes only, not failures): the newsletter is listed under Diligence documents, "30 Sep 2026" and "1 Oct" appear in the quoted passage, and the standing note is shown.

**Charter 2, `uc7a_2.py` (P26, P27)**
1. Open Kestrel Ridge and click "Show what changed" with no date. Assert:
   - "12 Jun 2026" is shown as the last meeting;
   - an "N dated items" answer line;
   - at least 3 items;
   - the 31 Jul 2026 revised-statement item;
   - 20 Aug 2026;
   - "Equity Long/Short Fund dated 31 Aug 2026";
   - 22 Sep 2026;
   - 28 Sep 2026;
   - a chip for every item.
2. Figures: 7,012,500 must be on screen. 7,050,000 and "6 business days" are soft checks.
3. Click the "Kestrel Ridge Macro Fund, valued 31 Jul 2026" link and assert it lands on `/centre/action/evidence/…`.
4. Open Cedarpoint Ventures and assert:
   - "Cedarpoint Ventures III" and "Cedarpoint Opportunities II";
   - commitments 6,000,000 and 5,000,000;
   - D last valued 31 Mar 2026;
   - "Still missing: the statement for 30 Jun 2026";
   - the open question ("30 June 2026", "has not arrived");
   - a DDQ in Diligence documents.
5. Set "Since" to 2026-01-01 and click "Show what changed". The answer line must be present. "45 days" and "auditor" are soft checks.

**Screens missing or confusing, from reading the code**
- `ui/src/v1/k5/routes.tsx:8-9`: nothing in the shell or the Consume landing links to `/centre/consume/managers`. `cxui/routes.tsx:7` shows a ProjectList at `/centre/consume`, and no grep hit links to the managers list. The scripts go by address, but a family-office user cannot find Consume > Managers by clicking. Action > Managers (`a5/ActionCentre.tsx:21`) does reach the manager pages.
- `ui/src/v1/k5/ManagersInbox.tsx:12-14`: the fund line says "N days late", counted in calendar days. P26 expects "6 business days late" for the August statement. `tests/v1/test_seed_10uc.py:211` asserts 8, so the screen will show "Received 8 days late". I made that a soft note.
- `ui/src/v1/k5/ManagerPage.tsx:68`: each change line shows its date and a chip, but the amended-NAV line may not carry "7,050,000 to 7,012,500". The change text is built in `sh_platform/v1/k5_managers.py`, and the test only expects "revised statement … arrived". If the old figure is not on screen, that soft check will show it.
- `ui/src/v1/k5/ManagerPage.tsx:71`: the passage chip prints the file name and line numbers ("file, lines a to b"), which is an engineer-style chip for a family-office user.
- `ui/src/v1/k5/ManagerPage.tsx:60`: the date field "Since" is empty by default, and the answer reads "Since 12 Jun 2026" only after the click. The Cedarpoint last meeting is 19 May 2026. DDQ facts (45 days, auditor change) are unlikely to appear unless the DDQ's date falls inside the chosen "Since" range, and the DDQ is dated 5 Mar 2026.

---

Files: `<repo>\tests\e2e_10uc\uc3a_1.py` and `uc3a_2.py`. Both are standalone (they share a duplicated helper block) and take `--base --creds --out`. They log in as Mei Chen, the analyst, read her sign-in from the creds file (prefix `mei.chen.`) and never print the password. They compile and parse cleanly, but only `ast.parse` and `py_compile` were run; no browser run has happened.

**Run result: unrun.** `docs/plan/v4-landings/D.md` doesn't exist; the folder holds K1.md to K8.md. `ui/dist/index.html` (15:57) is also older than the newest `ui/src/v1/k4` files, so neither condition is met.

**uc3a_1 — Action › Managers, September expected vs received (P09).** Output goes to `DIR/uc3a_1/NN-*.png` and `result.md`. Expected figures come from `10uc_universe.json`, and I left out the A amended row because the seed doesn't load it.
1. Open the sign-in page, sign in, open Action, then the Managers tab (falls back to `/centre/action/managers`).
2. Check all six manager names appear, the "Action" heading shows, and the Managers tab is marked current.
3. Check each manager card reads "N expected · M received · 0 late", with N and M derived from the universe.
4. Check each fund shows "Statement for 30 Sep 2026, due 14 Oct 2026" with its received date: A 2 Oct, B 1 Oct, E 8 Oct, H1 6 Oct, H2 7 Oct, L1 and L2 1 Oct.
5. Check C and D read "Not due yet", with no received date and no "Late n".
6. Check E's line says "unverified" and A, H1 and H2 say "estimate".
7. Check "Draft a follow-up" is enabled only on Cedarpoint (D's June is the one missing statement) and the other cards say "Nothing is late".
8. Check "30 Sep 2026" appears with no "USD 0", then run the screen-hygiene scan.

**uc3a_2 — late and missing statements, "Draft a follow-up" for Fund D (P10, P11).**
1. Open Action › Managers.
2. For H2 August, E June and D March, open the manager page and find the "Statements and revisions" line. It must show the received date (22 Sep, 24 Jul, 21 Apr) and the lateness number (6, 8, 5) next to "late".
3. On the Cedarpoint card, check "Still missing: the statement for 30 Jun 2026, due 14 Jul 2026" and that it says 63 days overdue.
4. Press "Draft a follow-up" and check the draft text. It must contain Hana Sato, "Cedarpoint Opportunities II", 30 Jun 2026 and 14 Jul 2026, and name no other fund.
5. Check the "(not sent)" label, the "has not been sent" note and the "Copy the draft" button.
6. Press "Copy the draft" and check "Copied." shows and the clipboard holds the draft.
7. Check the only non-GET request is the `/followup` draft call, with no send or mail request.
8. Run the hygiene scan.

The hygiene scan looks for undefined, NaN, null, uuids, "Error", Traceback and the app's own failure sentence.

**Expected failures, found while reading the code.** I wrote these as hard checks, so uc3a_2 should exit 1 on the first three. If the product is meant to behave this way, these are bugs.
- **No address to Hana Sato.** The draft opens "Dear {manager name} team" (`sh_platform/v1/k5_managers.py:219`). The contact name Hana Sato is never used, so the P11 "addressed to Hana Sato" check will fail.
- **No lateness for past statements.** `_fund_row` (`k5_managers.py:140-161`) judges only the latest month end. Past received-late statements (H2 Aug 6, E Jun 8, D Mar 5 business days) are not flagged on the inbox. The manager timeline (`ui/src/v1/k5/ManagerPage.tsx:110-111`) shows only "received <date>", with no lateness. P10 says "Action > Managers > late", but no such view exists, so the lateness-wording checks will fail.
- **Calendar days, not business days.** `_earlier_missing` (`k5_managers.py:136`) counts calendar days, so D June reads "87 days late". P11 expects 63 business days, so the "63" check fails.
- **Late versus missing wording.** `ManagersInbox.tsx:19-26` says "Still missing … N days late". The universe calls the same item a missing statement, and the screen never uses the word "missing" outside "Still missing".
- **Hard-coded "Illustrative" nav.** Not checked.

**Possible failures on the first run (guesses, not read from code).**
- Fund names on screen are assumed to equal the universe `canonical_name`. The manager name is `f["manager"]` from the warehouse (`k5_managers.py:75-90`), so an id could appear instead.
- The nav links "Action" and "Managers" are assumed to exist with exact names. If they don't, the scripts fall back to the address.
- The "estimate" and "unverified" words rely on the raw value status being printed in `ManagersInbox.tsx:22`, which is not user-friendly copy.
- en-GB dates in Chromium may print "Sept". The scripts' date matcher accepts "Sep" or "Sept".

---

Files:
- `<repo>\tests\e2e_10uc\uc5a_1.py`
- `<repo>\tests\e2e_10uc\uc5a_2.py`

Both scripts compile with `python -m py_compile`. Run result: **unrun** for both. `docs/plan/v4-landings/D.md` does not exist, so I did not start the test environment.

Both scripts take the universe figures from `10uc_universe.json` (`limits_check_30_sep`). Both log in as Mei Chen (analyst) from the creds file. They set "Check as at" to the universe as-of date, 2026-10-09, and press "Run now" on the Limits card. Each screenshot goes to `DIR/uc5a_N/NN-step.png`. The scripts check the page text for undefined, null, NaN, raw ids and error text. They write `result.md` and exit 1 on a failure.

**Charter 1, `uc5a_1` (P17 Harborview)**
1. Signed in: Mei Chen (analyst) is past the sign-in page.
2. Limits card after the run: it reads "2 limits breached" and the rule wording shows 5%.
3. Limits card causes: Harborview Semiconductor is listed with "real breach".
4. Case opened from Action > Cases (the "Limit breached · Harborview Semiconductor" row). The "What was compared" text must show the share (5.75, accepted as 5.75, 5.8 or 5.7), "above", a 5% limit and "Cause: real breach".
5. Case page: heading names Harborview Semiconductor, and a "Where is this from?" button is present.
6. Second login as Sofia Reyes (Risk, participant): she sees "2 limits breached" and no "Run now" button.

**Charter 2, `uc5a_2` (P18-P20)**
1. Limits card: Cedarpoint Ventures is listed with "stale data".
2. Case: 56.5% against 55%, "Cause: stale data", and "N input value(s) are older than 90 days".
3. Action Desk: exactly two rows titled "Limit breached", none for Pacific Rim, PRC29, Evergreen Funds, hedge or listed equity (P20).
4. PRC29: "Needs a class", "Pacific Rim Convertible 2029" and 2.72% must be on the Limits card (P19).
5. Within-limit rows: 80.61% for listed equity and 54.95% for hedge funds must be on the Limits card.

Steps 4 and 5 of charter 2 will fail against the current UI, because nothing in the UI shows that text (see the first item below).

**Missing or confusing, found by reading the code**
- `ui/src/v1/a5/ReconPage.tsx:44-50`: the Limits card shows only the breach count, rule wording and a "title: cause" list. There is no "Needs a class" question for PRC29 and no within-limit rows or percentages (P19, P20). I found no "Needs a class" string anywhere under `ui/src`.
- `sh_platform/v1/e3_recon.py:~262`: the case description formats the share with one decimal. Harborview's true share is 5.7476%, so it prints "5.7%", not the universe's 5.75%. The scripts accept 5.7, 5.8 or 5.75.
- `ReconPage.tsx:47`: when a check has no `rule_words`, the card prints "signed rule {version id}", a raw id on screen. The scripts only scan the Limits card, so this does not show up there.
- `ui/src/v1/e4/CasesPage.tsx:25`: case links point to `/centre/desk/<id>`. They only reach `/centre/action/cases/<id>` through the redirect in `ActionCentre.tsx` (`Stay`). If that redirect misfires the click lands on the wrong route.
- `ui/src/v1/a5/ReconPage.tsx:32`: the date field defaults to the real current date, not the demo as-of date. The scripts set it explicitly.
- The Cases list (`CasesPage.tsx`) does not show the cause (real breach or stale data); you only see it by opening each case.
- The scripts match the Limits card by `li.ds-card` and the case section by `section[aria-label='What was compared']`, because those elements have no better role or label. The selectors assume the Limits card heading text stays "Limits".
- The creds lookup matches the lines starting `mei.chen.evergreen@` and `sofia.reyes.evergreen@`. If the creds file uses another domain suffix, it still matches on that prefix.

---

Files: `<repo>\tests\e2e_10uc\mapa_1.py` and `<repo>\tests\e2e_10uc\mapa_2.py`. Both pass `python -m py_compile`.

**Run result: unrun.** `docs/plan/v4-landings/D.md` does not exist, so I did not build a test copy or start a server.

Both scripts log in as the head of data, Anita Rao (analyst). The Map is analyst and company admin only (`ui/src/shell/roles.ts:32`). Each reads the password from the creds file, picks the line whose email contains `anita.rao`, and never prints or saves it. Both walk the journey at 1440x900, take a screenshot per step, and fail a step if the page shows raw ids, `undefined`, `null`, "error" or "exception" text. Each writes `DIR/mapa_N/result.md` and exits 1 on any failed step. Steps marked soft below record a note in `result.md` but do not fail the run.

**Charter 1 (`mapa_1.py`, Data flow tab):**
1. Sign in.
2. Open `/centre/map`: heading "Map", its subline, and 4 tabs, with Data flow first.
3. Region columns: Sources, Files, Raw data, Ready for reports, Dashboards and People (Company model is optional).
4. Four source boxes: Fund administrator, Trading system export, Manager statements by email, Market data file.
5. Side panel shows the "Click a box" hint before any click.
6. Click Fund administrator: owner "Mei Chen", the Last load, Fed by and Feeds sections, and a button for "Files from Fund administrator".
7. Follow into the files box: owner Mei Chen and a last-load date such as "8 Oct 2026". This is the check most likely to fail if the seed has no landed files.
8. Exactly one box is marked chosen, and `focus=` is kept in the address.
9. Ready-for-reports boxes come from the P33 gold tables in the JSON. Status reads "Live" and the owner is named.
10. Raw-data boxes come from the P33 bronze tables in the JSON.
11. Click the dashboard box: its audience Daniel Foo and Raj Patel appears in the People column and in the panel (P33).
12. Click the chosen box again: the panel clears.
13. `?tab=flow&focus=source%3Aadministrator` opens focused.
14. `focus=nope` shows the hint with no error.
15. Subline "Everything here is read from your records".

**Charter 2 (`mapa_2.py`, Process maps, Definitions, Health, "Open in the map"):**
1. Sign in.
2. Process maps: a chip for "Monthly investment report in USD and SGD", a Signed line with a date, and a "Process map" group. Steps 1 to 6 are named from the JSON, and 4 "Manual" pills are expected (P32).
3. Soft: step owners (Mei Chen, Raj Patel, Daniel Foo) appear on the lanes.
4. Soft: clicking step 2 shows its control or exception text.
5. Definitions: at least one concept, the project title, Owner, Version and a signed date, and no "No wording yet".
6. Soft: "Net worth", "Cash" and "Holdings" appear (tiles K01 to K03).
7. Health: seven column headers, four source names, "Owner Mei Chen", and arrival words (On time, Late by, and so on).
8. Soft: the Manager statements row counts 2 stale values (Fund C 101 days, Fund D 192 days, P07).
9. Open in the map: on `/centre/action`, click "Where is this from?", expect an "Open in the map" control, click it, and expect `/centre/map` with `focus=`. This step will fail as the code stands (see item 1 below).
10. `?tab=definitions&focus=<first concept>` marks that concept with an outline.
11. `?tab=processes&focus=not-a-real-intent` falls back to the first signed process.

**Missing or confusing screens found while reading the code:**
1. "Open in the map" does not exist in any TSX. `ui/src/v1/a5trail/TrailPanel.tsx:25-47` has only a Close button, and the only mention is a comment at `ui/src/v1/k3/routes.tsx:4`. Charter 2 step 9 will fail until it is built.
2. The Map is reachable by two different bar items. `ui/src/shell/copy.ts:13` has "COMPANY MAP", which goes to `/centre/intent/graph`. `ui/src/shell/copy.ts:25` has "MAP", which goes to `/centre/map`. The scripts navigate by URL to avoid the ambiguity.
3. `ui/src/v1/k3/ProcessTab.tsx:27` shows no step detail (control, exception, system) when a step is clicked. P32 expects those details, so the soft step 4 may note it.
4. `ui/src/v1/k3/FlowTab.tsx:27` shows "Last load" as "Not available yet" for every source box, because source nodes carry no `last_load` (`sh_platform/v1/k3_map.py:129-132`). Only the Files box has a date.
5. The Trail panel is only mounted on the Action home page (`ui/src/v1/a5/ActionCentre.tsx:64`) and only for cards that come from a case. If the seed has no case cards, charter 2 step 9 fails on "no Where is this from? button".

---

Both scripts are written and compile with `py_compile`, but unrun, so nothing has been tested against a live UI yet. `docs/plan/v4-landings/D.md` doesn't exist, and `ui/dist/index.html` (15:57) is older than `ui/src/v1/k4` (16:36). I started no servers and ran no vite.

**Files**
- `<repo>\tests\e2e_10uc\shell_1.py`
- `<repo>\tests\e2e_10uc\shell_2.py`

Both take `--base`, `--creds` and `--out`, and write `DIR/shell_N/NN-<step>.png` plus `result.md`. They exit 1 on any FAIL. Rows marked "note" are findings and don't fail the run. Every step also scans the visible text for `undefined`, NaN, `[object Object]`, tracebacks, uuids and role codes. Passwords are read from the creds file (rows whose company is `evergreen`) and never printed.

**Charter 1, `shell_1.py` (Shell)**
- People and roles are read from the `people` list in `10uc_universe.json`: Daniel Foo (sponsor), Raj Patel (approver), Sofia Reyes (participant), Mei Chen and Anita Rao (both analyst; one analyst, Mei, is tested), Grace Ong (company_admin).
- For each person, the script logs in and asserts they land on `/centre/action`.
- The bar is checked against `barFor` in `ui/src/shell/roles.ts`:
  - sponsor and approver: INTENT, ACTION, CONSUME
  - participant: INTENT, ACTION
  - analyst and company_admin: INTENT, ACTION, BUILD, CONSUME, MAP
- It clicks each bar link and asserts it opens with no refusal.
- For BUILD, CONSUME and MAP outside the person's role, it types the address. It asserts a refusal notice shows or the person is sent home, that the bar is unchanged, and that no raw text appears.
- A "note" row checks that the refusal reads "You do not have access to this".
- In the account menu, Settings is asserted for analyst and company_admin only, and Sign out for everyone.

**Charter 2, `shell_2.py` (Settings)**
- **Today cards:** Figures come from the universe: P02 gives 180,000 and P08 gives 12,400.
  - Daniel needs a "Revised" card with 180,000 and "manager-reported valuation".
  - Mei needs "Break" with "a difference of" and 12,400, plus the same Revised card.
  - Raj needs a "Break" card.
  - Sofia needs a "Limit" card.
  - Across all cards, no word may be a raw kind. A "Limit breached…" headline must read Limit, "Statement missing…" must read Late, and a dashboard card must read Shared or Refreshed.
- **Late and Shared:** Mei's Managers tab must show "N days late". Daniel's Shared card is only a note, because it exists only after the dashboard is shared in the run.
- **Settings, Grace (company_admin):** She opens Account menu, Settings, Agent runs and cost. The table "Runs by agent and day" must have the columns Agent, Day, Runs, Failed, Tool calls, Cost.
  - Agent names must be "North, the industry expert", "Span, the data engineer" or "Lumen, the analyst".
  - Cost must be `USD x.xxxx` or "Not available yet", never zero. Counts must be whole numbers, and the "Failed runs" heading must show.
  - Filtering to 2020-01-01 must show "No agent runs on that day."
  - She also opens the six other Settings sections.
- **Settings, Mei (analyst):** The script asserts she gets the runs or one plain sentence with no codes.
- **Settings, Daniel (sponsor):** The script asserts he has no Settings link and that typing `/centre/settings/runs` sends him back to Action with a notice.

**Findings from reading the code**
1. **Refusal wording:** The charter says the refusal should read "You do not have access to this". The shell gives a different sentence: "That page is not part of your work here, so you are back on your start page." It appears at `ui/src/shell/copy.ts:55` (`refused`) and renders at `ui/src/shell/CentreShell.tsx:81`.
   - "You do not have access to this" appears only for a 403 from the server (`ui/src/copy.ts:28`) or on the extraction page (`ui/src/v1/x5/ExtractionPage.tsx:52`).
   - The scripts record this as a "note" (finding), not a failure. If the plain phrase is a hard requirement, promote those rows to FAIL.
2. **Open routes:** `consume` (`ui/src/v1/cxui/routes.tsx:7`) and `map` (`ui/src/v1/k3/routes.tsx:5`) have no role gate; `ui/src/v1/p3/routes.tsx:15` says this is deliberate and the server decides. A typed address for those may open the page for a role without the bar link. If it does, the "typed address" row fails; the Map shows "Source health is for the data team." only on the Health tab (`ui/src/v1/k3/HealthTab.tsx:17`).
3. **Settings access:** `canSettings` in `ui/src/shell/roles.ts` lets analysts see "Agent runs and cost" (`ui/src/v1/s1/SettingsPage.tsx:54`), but the comment at line 12 says the server allows only the company administrator. An analyst may therefore get a server error sentence there.
4. **Today card text:** Status words come from `statusWord` in `ui/src/v1/e5/api.ts:50-60`. Every Statement-kind card reads "Late" even when the server sent "Stale" (`sh_platform/v1/e5_pulse.py:233`). The headline wording is not fixed in the universe, so the scripts match by word and figure, not by headline.
5. **Pill selector:** There is no testid or aria label on the Today pill (`ui/src/v1/e5/TodayPage.tsx:44`). The script takes the first line of each card list item as the status word, so a markup change will break it.

---

Both scripts are written and pass `python -m py_compile`. They are **unrun**: `docs/plan/v4-landings/D.md` does not exist (only K1 to K8), and `ui/dist/index.html` (15:57) is older than `ui/src/v1/k4` (16:36). So I made no test copy and started no server.

**Files**
- `<repo>\tests\e2e_10uc\uc6a_1.py`
- `<repo>\tests\e2e_10uc\uc6a_2.py`

**Shared behaviour**
- Each script logs in as Raj Patel (the approver, read from the universe JSON) through the login page, using `requestSubmit`. The password comes from the creds file and is never printed or saved.
- Every step is screenshotted to `DIR/uc6a_N/NN-<step>.png` and recorded in `result.md`. The script exits 1 on any failed step.
- After every step it checks the screen for `undefined`, `NaN`, uuids, `mv-…` ids, `EG-…` or `MGR-…` codes, error text and visible alerts. Any hit fails that step.
- All figures, dates and fund, entity and manager names come from `docs/test/10uc_universe.json`.

**uc6a_1: Office view › Liquidity (P21, P23)**
1. Sign in as the approver.
2. Open `/centre/consume/office`. It tries a link named "Office view" first and falls back to the address. If it had to type the address, it logs that as an observation.
3. Liquidity section shows a card for Evergreen Holdings, Evergreen Family Trust and Entity B.
4. Entity B shows available cash USD 880,400. Its three rows match the universe figures:

   | Row | Calls | Distributions | Cash after calls |
   |---|---|---|---|
   | Within 30 days | 1,050,000 | 0 | -169,600 |
   | 31 to 60 days | 250,000 | 0 | -419,600 |
   | 61 to 90 days | 0 | 0 | -419,600 |
5. The "Not confirmed yet:" line names Saltmarsh Infrastructure Fund II, USD 600,000, due 30 Oct 2026. It must not name the Cedarpoint Ventures III call.
6. "Where is this from?" on Entity B lists:
   - the Fund C call (USD 450,000, due 20 Oct 2026) as confirmed;
   - the Fund E call as "waiting to be confirmed";
   - the Fund D call (USD 250,000, due 4 Dec 2026) as confirmed;
   - cash "as at 8 Oct 2026".
7. Evergreen Holdings shows a 320,000 distribution in the 31 to 60 day row. The source list reads "Evergreen Growth I: distribution USD 320,000 due 16 Nov 2026, waiting to be confirmed", and no "Not confirmed yet" line appears.
8. The Family Trust shows USD 1,150,000 with no calls and no flags.
9. No "Not available yet" appears in Liquidity.

**uc6a_2: Finance case, after-call cash, commitments (P22, P24)**
1. Sign in as the approver.
2. Action › Cases (the "Action tabs" navigation): exactly one row titled "Fund the capital call", with size USD 450,000 and "Due 20 Oct".
3. Open the case. The heading carries "Fund the capital call" and "USD 450,000", and the History section is visible.
4. The case page names Cedarpoint Ventures III and does not mention Saltmarsh Infrastructure Fund II.
5. Back on the Office view, Entity B shows available cash USD 880,400 and the same row figures as uc6a_1, including USD -169,600 within 30 days.
6. The negative figure must be explained in words as a shortfall.
7. USD 430,400 (cash after the confirmed call only) must be visible.
8. "Still to be called" is USD 4,550,000 for Evergreen Holdings and USD 8,900,000 for Entity B.
9. For each of Northgate Partners, Bluewater Capital, Cedarpoint Ventures and Saltmarsh Real Assets, it opens the profile and checks the Commitments table. For each fund it checks the entity name, the committed, called and not-yet-called figures with currency, and that called does not exceed committed. These are the P24 figures.

Steps 4, 6 and 7 of uc6a_2 will probably fail on the current screens, for the reasons in the findings below.

**Missing or confusing screens found in the code**
- **No way into the Office view or Managers.** The Consume landing is `ui/src/v1/cxui/routes.tsx:7` (`ProjectList`); `ui/src/shell/copy.ts:9,19` also points Consume at `/centre/consume`. Neither it nor `ui/src/pages/ConsumeCentre.tsx:58-77` links to `/centre/consume/office` or `/centre/consume/managers`. P21 to P24 name "Consume > Office view" and "Managers" as their places, but only the address reaches them.
- **No confirmed-only figure.** `ui/src/v1/k4/OfficePage.tsx:170-172` shows one "Cash after the calls" per row, which includes the unconfirmed Fund E call. The 430,400 figure (cash after the confirmed call only) is not on screen anywhere, so uc6a_2 step 7 will fail unless that is added.
- **Shortfall unlabelled.** `OfficePage.tsx:172` prints the negative figure as "USD -169,600" with no word "shortfall" and no warning tone.
- **Capital-call case page is thin.** `ui/src/v1/a5/CaseView.tsx:13,53-62`: `NO_STATEMENTS` lists only `break` and `limit_breach`. A `capital_call` case therefore shows "Evidence for this case" with "No statements are linked to this case" (line 26). The case description, which holds the fund name and due date, is not shown, so a person cannot tell which fund to pay.
- **Two headings in Action › Cases.** `ui/src/v1/a5/ActionCentre.tsx:73` ("Action") and `ui/src/v1/e4/CasesPage.tsx:20` ("Action Desk") both render at heading level 1. The tab is "Cases" but the page is "Action Desk". The script targets "Action Desk".
- **Zero uncalled.** `OfficePage.tsx:164` prints "Still to be called USD 0" for the Family Trust, which has no commitments. The copy rules say a missing figure should read "Not available yet", never zero.
- **Two money formats.** Office uses `USD 15000000`, the Managers profile `USD 15,000,000.00` (`ui/src/v1/k5/api.ts:38-41`), and the case list is en-GB. The script parses amounts as numbers so this does not break it, but the formats are inconsistent.

---

Both scripts are written and compile with `py_compile`. I did not run either one: `docs/plan/v4-landings/D.md` doesn't exist (only K1.md to K8.md), so the "unrun" condition applies.

**Files**
- `<repo>\tests\e2e_10uc\uc10a_1.py`
- `<repo>\tests\e2e_10uc\uc10a_2.py`

Both run at 1440x900, log in through the login page (`requestSubmit`), read passwords from the creds file without printing them, and take screenshots to `DIR/uc10a_N/NN-step.png`. Both write `result.md` and exit 1 on a failure. Every clean-screen check scans for raw ids, error words and "undefined". Clicks fall back to a DOM click if a plain click times out. All names and figures come from `10uc_universe.json`.

**Charter 1: Mei Chen (analyst) and North**
1. Sign in; check the Intent link is in the bar.
2. Open `/centre/intent`, or continue an open conversation, and send the opening line built from the project title, the sponsor Daniel Foo and the "3rd business day of each month" deadline.
3. North answers and the Documents panel shows "Intent of work".
4. Send the six process steps (name, who, system). Assert the "Process map" group has at least 4 `Step n:` buttons, a key word from each of the 6 step names, and the systems File drop, Excel and Email.
5. Send the sources and the three tile names (Net worth by entity, Cash by entity, Holdings by status). Assert the intent document shows Goal and Sources.
6. Press "That's right" and nudge North until "Hand to the architect" appears. The header must be the project title, containing "investment report", not an id and not "Talk to North".
7. On the intent of work page: eight sections, same header, settle any open questions, press Sign, check the confirm sentence, then "Yes, I sign". Assert "Signed by Mei Chen".
8. Back in the thread, press "Send to Build". Assert "Sent to Build", "head of data has a card in Action", no raw id and the title still in the header.
9. Write `handoff.json` with the project title for charter 2.

**Charter 2: Anita Rao (head of data) in Build**
1. Sign in as Anita. As setup, Leo Park (data engineer) proposes the plan, because Anita can't approve a plan she proposed herself (`b6_routes.py:70`).
2. Check the "<title> is ready for Build" card in Action and "Open in Build". The card check only applies when charter 1 ran first.
3. Build page: header is the title; the project list row shows stage and build state.
4. Sources show owners. Tables show bronze and gold sections; the P33 table names (the two bronze and two gold tables) are required when the project is the universe one rather than a fresh one.
5. Approval shows "Proposed by" and "Waiting for the head of data". Press "Approve the plan and the model change" and assert "Approved by Anita Rao".
6. Pipeline: "Try it on a copy" must finish without a failed step and show rows. "Go live" must record a live run.
7. Set "Every month" at 07:00, save, reload, and check it persisted.
8. "Download the Airflow file": a `.py` file with "DAG" that names the gold tables.
9. `/centre/build` shows the project as Live.

**Screens I found missing or confusing**
- `ui/src/v1/i6/ConversationPage.tsx:258` prints "for project <id>" after Send to Build, and `ui/src/v1/p1/ProjectTag.tsx:22` shows "Project <id>" in the Intent header. Both put a raw id on screen, so the clean-screen checks should fail there.
- `ui/src/v1/b6/ProjectsPage.tsx:137` uses the raw project id as the link text in the Build list. It also searches by "Project id or title" (line 129).
- `ui/src/v1/b6/BuildPage.tsx:19` (`useProjectTitle`, `s1/useProjectTitle.ts:6`) shows the id as the header until the project list loads.
- `ui/src/v1/i6/Swimlane.tsx:335`: the "Manual" tag matches only the words manual, spreadsheet, excel or "by hand". P32 flags steps 1 to 4 as manual, but the File drop (step 1) and Email (step 3) steps won't be tagged unless the text says "manual".
- `ui/src/shell/copy.ts:8` still points the old BUILD CENTRE link at `/centre/build/ops`. The four-centre bar uses `/centre/build`.
- `b6_routes.py:70`: the same seat (analyst) can propose and approve, so the head of data can't approve a plan he asked Span to propose himself. This is why the setup step uses Leo.
- If Mei already has an open conversation, `/centre/intent` redirects into it (`IntentWelcome.tsx:46`). The script handles that, but a fresh intent then needs another route.

---

Both scripts are written and compile with `py_compile`. I did not run them: `docs/plan/v4-landings/D.md` doesn't exist, and `ui/dist/index.html` was built Oct 9 15:57 against the cards that landed after it. A quick offline check showed the figures read from the JSON come out right (180,000, 7 Oct 2026, 1,648,000, issued 3 Oct 2026) and Daniel Foo's sign-in resolves.

**Files**
- `<repo>\tests\e2e_10uc\uc1b_1.py`
- `<repo>\tests\e2e_10uc\uc1b_2.py`

Both take `--base URL --creds PATH --out DIR`. They sign in as the sponsor, Daniel Foo, through the login form with `requestSubmit()`. Each step gets a screenshot at `DIR/uc1b_N/NN-<step>.png`. Each step also checks the screen for `undefined`, `NaN`, `[object`, a traceback, error text, UUIDs and ids like `exc:…`. A summary goes to `DIR/uc1b_N/result.md`, and the exit code is 1 on any fail. All figures come from `docs/test/10uc_universe.json`. Steps marked soft record an "info" row instead of a fail.

**Charter 1: Fund A revision card to case to evidence (P02)**
1. Sign in lands on `/centre/action`, with the Today tab and Daniel Foo shown in the bar.
2. A Today card appears that contains "Revised" and "Evergreen Growth I" (or "Fund A"). It shows 180,000 and "7 Oct 2026", and it has an "Open case" link and a "Where is this from?" button. If the card isn't under "Needs me", the script tries "Worth a look".
3. "Where is this from?" opens the trail panel, which must show numbered steps. The panel is then closed.
4. "Open case" goes to `/centre/action/cases/…`. The heading must contain 180,000, the page must name the fund, and a History region must be there.
5. The case's Evidence region must list a statement valued 2026-09-30 labelled Current, and the script opens it.
6. The evidence page heading must contain the fund and "2026-09-30". The Current statement must show 10,180,000 and the 7 Oct receipt date. The Superseded statement must show 10,000,000. The Current statement must also give "Page n, line n", and the "What was read" table must have rows.

**Charter 2: Why did this move on the liquid book, and the CIO Brief (P06)**
1. Sign in and click CONSUME.
2. Look for a link to the Office view.
3. On the Office view, Holdings must show "Evergreen Liquid portfolio" and 41,200,000. The "Liquid book" row under "Issued versus known now" must show 41,200,000 twice and read Official.
4. A "Why did this move" button on the Office view must give 39,552,000, 41,200,000 and 1,648,000.
5. "Open the CIO Brief" must land on `/centre/consume/brief/…`. The page must say "Issued 3 Oct 2026", the liquid row must show 41,200,000, and the Fund A row must show 10,000,000, 10,180,000 and Revised.
6. "Why did this move?" on the Fund A line must give an explanation containing 10,180,000 and 180,000.
7. Soft: the same button on the liquid line must give the three P06 figures.
8. Soft: on Consume, open the project "Monthly investment report in USD and SGD" and its first dashboard. Click "Why did this move" on each accepted tile and look for the three P06 figures.
9. At least one of the routes above must show 39,552,000, 41,200,000 and 1,648,000. If none does, this step fails.

**Missing or confusing screens found while reading the code**
- **No Office view link (P06 route):** Consume (`ui/src/v1/cxui/ProjectList.tsx`) lists projects only. The Office view, and so the CIO Brief link on it (`ui/src/v1/k4/OfficePage.tsx:109`), is reachable only by typing `/centre/consume/office`. Nothing else links to it (grep of `ui/src`).
- **No "Why did this move" on the Office view:** `OfficePage.tsx` has no such button, although P06 says Consume > Office view > Why did this move. Charter 2 step 4 will therefore fail on the current code.
- **No liquid-book button on the Brief:** `BriefPage.tsx:50` shows the button only for changed lines (`api.ts` `toBrief`, `changed`). The liquid book is unchanged, so it gets none.
- **Wrong answer for the liquid book:** the server's `explain` in `sh_platform/v1/e5_brief.py` (about line 258) only talks about a manager-reported valuation. For an unchanged line it would say it "has not changed since the report was issued", not 39,552,000 to 41,200,000.
- **Tile route likely fails:** the tile "Why did this move" (`ui/src/v1/cxui/TileCard.tsx:40`, `cx_lumen.explain`) gives totals of each tile's own series. The seeded tiles (Net worth by entity, Cash by entity, Holdings by status) likely won't give the liquid-book-only 1,648,000.
- **Project ids on screen:** `ProjectList.tsx:36` shows the project id in each project button ("id · title · stage"), against the screen-copy rule. `ProjectList.tsx:39` repeats it in "Dashboards of {id}".
- **Today card link goes to a case, not evidence:** the card's "Open case" link (`e5_pulse.py:169`) goes to the case, and the statement is reached from the case's "Evidence for this case" list (`CaseView.tsx`). The card has no direct evidence link.
- **Jargon in the evidence page and the reconciliation field list:** `ui/src/v1/e2/EvidencePage.tsx:60` shows the raw field name (`f.field`) in "What was read". If that is a column name, it breaks the plain-words rule. I couldn't check what it holds without running.
- **Case page link back:** `CasePage` has an "All cases" crumb to `/centre/desk`. The Action centre's click handler in `ActionCentre.tsx` rewrites it.

Two assumptions I couldn't confirm without running. The Today card headline must contain "Evergreen Growth I" or "Fund A". The case's evidence list must show `valuation_date` as ISO text (`2026-09-30`).

---

Files:
- `<repo>\tests\e2e_10uc\uc4a_1.py`
- `<repo>\tests\e2e_10uc\uc4a_2.py`

Both compile with `py_compile`. **Run result: unrun.** `docs/plan/v4-landings/D.md` does not exist, and `ui/dist/index.html` (9 Oct 15:57) was not checked against `ui/src/v1/k4`. I did not start any servers or touch product code.

Both scripts take `--base --creds --out`, read the universe JSON, and log in as several people (one fresh browser context each). They screenshot every step and write `result.md`, and exit 1 if any step fails.

**Charter 1 (uc4a_1, P14).** Role fact: the approver (Raj Patel) has no Build centre and no architect or data-engineer seat. So the walk uses the people who can act in Build.
1. Raj opens `/centre/build`. It asserts he is turned back and there is no Build link on his bar.
2. Leo Park (data engineer) opens the Build project list, then walks each plan looking for `gold_<slug>_benchmark_monthly`.
3. Leo opens that table and the script asserts its columns `benchmark_code`, `portfolio_return`, `benchmark_return` and `difference`. It asserts "Waiting for the head of data".
4. Anita Rao (head of data) presses "Approve the plan and the model change" and the script asserts "Approved by Anita Rao".
5. Leo presses "Try it on a copy". It asserts "Sandbox run, plan version N", that the run is not failed, and that the benchmark table is in the steps.
6. Raj opens Consume and the script asserts a "benchmark" tile with 2.7072, 2.2602, 4.1667 and 1.9065, also accepted to 2 dp.

Steps 3 to 5 report "not reached" if step 2 finds no plan.

**Charter 2 (uc4a_2, P15).**
1. Raj opens `/centre/action/cases`. It asserts exactly one row titled "Agree the definition of benchmark EG-OFFICE-BLEND".
2. He opens the case. It asserts the heading and "History".
3. It asserts the case says "still being defined" and "certified report", and shows no "No statements are linked" noise.
4. It asserts the case names EG-OFFICE-BLEND.
5. Raj opens `/centre/settings/rules` and is turned back.
6. Anita opens Settings > Rules. It asserts "The rules the figures follow" and a benchmark mention (v2 in progress). She also sees the same single case.

**Screens I found missing or confusing.** I expect several of these steps to fail on a real run.
- **No benchmark gold table in any plan.** The Evergreen plan `data/evergreen/build/prj-bfd3c588/plan-v1.json` is live with 4 tables and no benchmark table. The SOW has KPIs K01 to K03 only. `sh_platform/v1/b6_span.py:202-205` adds the table only when a KPI mentions "benchmark". Span's chat path (`b6_span.py:376-380`) uses `gold_tables`, not `benchmark_table`, so asking Span in chat will not produce it. A live plan also has no "propose again" button (`ui/src/v1/b6/BuildPage.tsx:72`, `Steps.tsx:68`), so the table only appears after a new intent with a benchmark KPI. Step 2 of charter 1 will fail on the seeded data.
- **P14 figures appear on no screen.** There is no "portfolio vs benchmark" tile. `ui/src/v1/k4/OfficePage.tsx` has Holdings, Issued, NAV bridge and Liquidity only. No route returns the `k7_benchmark` comparison (see `tools/verify_10uc/uc4.py:p14` note). Step 6 of charter 1 will fail.
- **Role table.** `ui/src/shell/roles.ts:9` gives the approver no Build, and `roles.ts:34-35` gives no Settings, so P14 and P15 ("role: approver, Build / Settings > Rules") cannot be walked as written. The scripts assert the turn-back.
- **Policy question case page.** `ui/src/v1/a5/CaseView.tsx:13` only treats `break` and `limit_breach` as having no statements. A `policy_question` shows "Evidence for this case: No statements are linked to this case" (`CaseView.tsx:58-62`). Its description is never shown: "is still being defined. It cannot be used in a certified report. Who decides…" (`sh_platform/v1/k7_benchmark.py:26`). Steps 3 and 4 of charter 2 will fail.
- **Rules register.** `ui/src/v1/e3a/AdminRules.tsx` lists only rule codes from the universe (cash_tolerance and so on). Nothing in it mentions the benchmark or version 2, so the Settings > Rules check will fail.
- **Broken link.** `ui/src/v1/s1/SettingsPage.tsx:27` links to `/centre/action/cases/${exception_id}`, which is fine. `ui/src/v1/e4/CasePage.tsx:36` links back to `/centre/desk`, which only works through the redirect.

**Assumptions to check on the first run.**
- The creds file has lines of the form `email password`, as `uc3b_1.py` assumes.
- The Cases API is open to the approver.
- All six Build documents render open on desktop.

---

**Files**
- `<repo>\tests\e2e_10uc\uc1a_1.py`
- `<repo>\tests\e2e_10uc\uc1a_2.py`

Both pass `python -m py_compile`. I also imported them to check the money formatter and the universe lookups.

**Run result: unrun.** `docs/plan/v4-landings/D.md` doesn't exist. The folder holds only K1 to K8. I started no servers and ran no vite.

**How the scripts work**
- Sign-in fills the Email and Password labels, submits the form with `requestSubmit()`, and reads Daniel Foo's password from the creds file.
- Each step is screenshotted to `DIR/uc1a_N/NN-<step>.png` and recorded in `result.md`.
- A step that fails does not stop the journey. The script exits 1 if any step failed.
- After every step the script checks the screen for UUIDs, `stmt-` ids, undefined, NaN, null, error text and any visible alert.
- Figures come from `docs/test/10uc_universe.json`. Money is formatted the way `k4/api.ts` writes it, for example "USD 10,180,000".
- Both journeys start from the Consume centre and look for a link to the Office view. If there is none, that step fails and the script goes to `/centre/consume/office` by address so the rest still runs.

**Charter 1 (`uc1a_1.py`): Office view, holdings, USD/SGD (P01, P07, P16)**
1. Sign in as the CIO.
2. Consume page, then the Office view link.
3. Office view heading, four sections, USD pressed, SGD offered.
4. **Holdings, USD (P07).** Each fund row is checked for value and status word:
   - A: USD 10,180,000, Revised.
   - B: Official.
   - C: Stale, source dated 30 Jun 2026.
   - D: Stale, source dated 31 Mar 2026.
   - E: USD 9,950,000, Unverified.
   - H1 and H2: Estimated.
   - L1 and L2: Official.
   - PRC29 row: USD 1,122,000, "Needs a class".
5. Portfolio totals (16.58m, 22.875m, 22.75m, 41.2m) and the "All holdings" line (sum of those four).
6. "Where is this from?" on Fund A names 30 Sep 2026.
7. Issued table, as issued column (P01): 10,000,000 / 6,400,000 / 41,200,000 / 57,600,000 USD, and "issued 3 Oct 2026".
8. **SGD switch (P16, P01):**
   - The SGD chip is pressed and holdings reload.
   - A, B and E convert at 1.3412 or at 1.3388 (the 8 Oct fixing). The script reports which rate the screen used.
   - The USD original shows beside each SGD figure.
   - The issued table in SGD shows the total as SGD 77,253,120 and each line at 1.3412.
9. Switch back to USD: no SGD left in Holdings.

**Charter 2 (`uc1a_2.py`): issued vs known now, NAV bridge, "Where is this from?" (P02 to P05)**
1. Sign in.
2. Consume page, then the Office view.
3. **Issued vs known now (P01, P02).**
   - Fund A: 10,000,000 as issued, 10,180,000 known now, Revised.
   - B and Liquid book: unchanged and Official.
   - Total: 57,600,000 against 57,780,000. The 57,780,000 is derived from the 180,000 revision, since no planted fact states it.
4. "Where is this from?" under the issued table names the issue date, 3 Oct 2026.
5. **NAV bridge, four portfolio cards (P03 to P05).** For each card:
   - the investment view, the administrator NAV, and "Difference" are checked;
   - the Revisions, Timing, Exchange rates and Unexplained amounts are checked.

   | Portfolio | Investment view | Administrator NAV | Part of the difference |
   |---|---|---|---|
   | Growth | 16,580,000 | 16,400,000 | Revisions 180,000 |
   | Liquid | 41,200,000 | 41,200,000 | none, difference 0 |
   | Entity B | 22,875,000 | 22,525,000 | Timing 350,000 |
   | Funds | 22,750,000 | 22,550,000 | Timing 200,000 |

6. "Where is this from?" on Growth › Revisions names Evergreen Growth I, "revised since the NAV was struck", valuation dated 30 Sep 2026.
7. The same click on Entity B › Timing names Saltmarsh Infrastructure Fund II.
8. The same click on Funds › Timing names both Kestrel Ridge funds.
9. "Open the CIO Brief" shows Fund A 10,000,000 to 10,180,000, Revised, with a "Why did this move?" button.

**Missing or confusing screens found while reading the code**
- **No route to the Office view.**
  - `ui/src/v1/p3/ConsumeEntry.tsx` has no link to `/centre/consume/office`. `docs/plan/v4-landings/K2.md:23` and `:37` flag this as undone wiring.
  - `ui/src/pages/ConsumeCentre.tsx` also has no link.
  - `ui/src/v1/cxui/routes.tsx:7` mounts a Consume page with a project list, and `ui/src/v1/p3/routes.tsx` has no consume route yet.
  - Until that is wired, step 2 in both scripts will fail by design.
- **Several buttons share one accessible name.** `ui/src/v1/k4/OfficePage.tsx:73, 110, 139, 165` are all "Where is this from?". There is one per holding, per bridge part and per liquidity card, plus one in the issued section. A screen reader or role locator cannot tell them apart without row context. The scripts scope by row.
- **Nested `<main>` landmarks.** `ui/src/shell/CentreShell.tsx:84` and `ui/src/design/parts.tsx:34` (PageFrame) each render a `<main>`.
- **The Office view doesn't show P02's +180,000 (1.80%) change or the materiality flag.** The issued table shows only the as-issued and known-now figures. The delta is likely only on the Brief, which the script checks only for the two figures and "Revised".
- **The days stale (101 and 192) in P07 don't appear on the Office view.** Holdings shows only the valuation date in the Source column. The scripts assert that date instead.
- **PRC29 "Needs a class" is a guess for the Office view.** The planted fact places it on the Limits screen. If the Office holdings row doesn't show that phrase, step 4 of `uc1a_1.py` will fail on that line.
- **The Holdings SGD rate is not stated on screen.** Holdings are as of the current date, which is likely 1.3388, while the issued table converts at 1.3412. The scripts accept either rate for holdings, so confirm which is intended.

---

Both scripts are written and compile (`py_compile` passes). I did not run them: `docs/plan/v4-landings/D.md` does not exist (the folder has K1 to K8 only), and `ui/src/v1/k4` is newer than `ui/dist/index.html`.

**Files**
- `<repo>\tests\e2e_10uc\access_1.py`
- `<repo>\tests\e2e_10uc\access_2.py`

Each takes `--base`, `--creds` and `--out`. Each logs in through the login page, reads passwords from the creds file, takes a screenshot per step to `DIR/access_N/NN-step.png`, and writes `result.md`. Each exits 1 on any failure. Every step also checks the page for raw ids, "undefined" and error text.

**Charter 1 (access_1, 1440x900)**
1. Anita Rao (head of data) is the positive control:
   - The bar shows Intent, Action, Build, Consume and Map.
   - `/centre/build` shows the "Build Centre" heading.
   - She opens the signed project's build page, and its `/centre/build/p/<id>` address is saved for step 3.
   - The raw-id check is off for this one step (see the first finding below).
2. Daniel Foo (CIO):
   - His bar shows Intent, Action and Consume, with no Build or Map.
   - `/centre/build` is refused: he lands on `/centre/action` and sees "That page is not part of your work here, so you are back on your start page."
3. Daniel Foo opens the saved project address (where the plan is approved). It is refused the same way, and there is no "Approve the plan and the model change" button. `/centre/control` and `/centre/settings/rules` are refused too.
4. Raj Patel (Finance):
   - His bar has no Build and no Map.
   - He opens `/centre/map` directly. There is no "Raw data" or "Company model" column, and the Health tab says "Source health is for the data team."
   - `/centre/build` and `/centre/settings/model` are refused.
5. Sofia Reyes (Risk):
   - Her bar has no Build, Consume or Map.
   - Her account menu offers the "What the agents remember about you" link and no Settings or Control panel.
   - `/centre/build` and `/centre/settings/people` are refused.
6. Someone not signed in who opens `/centre/build` lands on the login page.

**Charter 2 (access_2, 390x844)**
Every step fails if the page is wider than 390px, and the failure message names the offending elements.
1. Daniel Foo logs in.
2. Today (`/centre/action`) shows its heading plus the Needs me and Worth a look filters. The cards and the first Dismiss button fit, and a card with the status word "Revised" exists (P02).
3. The Centres burger menu opens and leads to Consume.
4. Office view (`/centre/consume/office`) shows the four sections: Holdings, Issued versus known now, NAV bridge and Liquidity.
   - The Issued section carries the Fund A estimate and amended figures (10,000,000 and 10,180,000, P01/P02) and the word Revised.
   - Switching to SGD shows 77,253,120.00 (P16).
   - All figures are read from `10uc_universe.json`.
5. Mei Chen (analyst):
   - The Cases list has the 12,400 cash break row (P08). This step only notes sideways scroll and does not fail on it, because the list is outside the charter.
   - Opening that case, the heading carries 12,400, and the History and "What was compared" sections are visible.
   - Every button on the case page sits inside 390px.

**Screens missing or confusing**
- `ui/src/v1/b6/ProjectsPage.tsx:31` prints the raw project id next to the title in the Build list. That breaks the ui-copy rule, so the id check is off for that one step in access_1. In access_2, `CasesPage.tsx:30` shows a case number rather than a database id. If the numbers look like `proj-<hex>` the check will flag them.
- `/centre/map` (`ui/src/v1/k3/routes.tsx:5`) has no role gate in the UI, and v1 routes sit outside App.tsx's `RoleGate`. Finance reaches the page by address, and only the server filters what it shows. I read "unless allowed" this way and assert that no data-team layer appears. If you meant a hard refusal, access_1 will fail at that step by design.
- The Build approve button is shown only on the project's Build page, which the head of data reaches from the Build list. The CIO is blocked by the Build gate at `b6/routes.tsx:12`, not by anything on the approval itself.
- `ui/src/shell/copy.ts` still carries the legacy `bar` list, including `COMPANY MAP` pointing at `/centre/intent/graph` (K1 landing note item 2). The new bar uses `centres`, so it is harmless unless something still reads `bar`.
- Phone width is untested. I expect the Cases list (5-column table) and the Office view tables to be the likeliest sideways-scroll offenders; this is a guess from the TSX, not a run.

---

Both scripts are written and compile cleanly under `py_compile`. They are unrun: `docs/plan/v4-landings/D.md` doesn't exist, and `ui/dist/index.html` (15:57) has not been compared against `ui/src/v1/k4`.

**Files**
- `<repo>\tests\e2e_10uc\uc10b_1.py`
- `<repo>\tests\e2e_10uc\uc10b_2.py`

Each takes `--base --creds --out`, uses a 1440x900 viewport and logs in via `requestSubmit`. The creds file is read as `email password` lines, the same format as `tools/verify_10uc/uc10.py`. Each run writes `DIR/uc10b_N/NN-<step>.png` and `result.md`, and exits 1 on any failed step. Expected values come from `10uc_universe.json`. The step checks raw ids and error text by regex (`t-000001`, `dash-xxxxxxxx`, `undefined`, `[object`, `NaN`, `HTTP 4xx`).

**Charter 1 (`uc10b_1.py`): Lumen builds a tile and shares it**
- **Leo Park (the analyst who made the dashboard)** signs in.
- **Consume** lists the project "Monthly investment report in USD and SGD" and its dashboard reads "3 accepted tiles".
- **Dashboard** shows Net worth by entity, Cash by entity and Holdings by status, each Accepted, with "Data used:" lines. Nothing says "could not be loaded".
- **Gold tables** drawer lists `gold_investment_report_holdings_monthly` and `gold_investment_report_cash_daily`.
- **Lumen**, asked "Show net worth USD by entity per month as a line chart", replies "I have proposed one tile". Exactly one new tile appears, marked Proposed.
- **Accept** marks that tile Accepted, with its numbers.
- **Share panel** reads "Shared with: Daniel Foo, Raj Patel", both ticked. Clicking "Share with these people" again raises no error.
- **Daniel Foo and Raj Patel**, each in their own login:
  - **Today:** under "Worth a look" there is a card "<title> shared with you", status Shared, with an "Open dashboard" link.
  - **Dashboard:** the link opens the three planted tiles plus the new one, with "Read only" shown and no Accept button.

**Charter 2 (`uc10b_2.py`): view link, trail, identity refusal**
- **View link, for Daniel and Raj:** `/centre/consume/d/dash-0ad2b1c7` shows the title and the 3 Accepted tiles with numbers, and "Read only". There is no Accept, no "Not this" and no Lumen composer.
- **Trail, for Daniel and Raj:** "Where is this from?" on Net worth by entity opens the panel with at least 3 steps, each carrying a status word (Recorded, Waiting, Not recorded or Restricted). It contains no "@", and Close removes it.
- **Not shared:** Sofia Reyes and Mei Chen get the alert "not shared with you" and no tile.
- **Identity refusal, as Leo, two asks** (a users table with names, emails and roles; the access list and passwords):
  - **No tile added:** Lumen says it could not match the request, and nothing is added.
  - **If a tile does come back:** its "Data used" tables must all start with `gold_`.
  - **Either way:** no email address or password text may appear on screen.

**Assumptions the first run may expose**
- The login page is at `/login`, with fields labelled "Email" and "Password".
- The accepted-tile count reads "3 accepted tiles".
- The Lumen rules match the column names `net_worth_usd` and `entity`. I took these from the seeded `dash-0ad2b1c7.json` in the golden data.

**Screens missing or confusing**
- `ui/src/v1/cxui/DashboardView.tsx:22` shows the raw project id on the shared view ("Project prj-xxxxxxxx. Read only."). That breaks the ui-copy rule against showing ids.
- `ui/src/v1/cxui/ProjectList.tsx:40` shows `{p.id} · {title}` on the project button. The same page's heading reads "Dashboards of {pid}" (line 43). Both show the raw id.
- `sh_platform/v1/cx_lumen.py:~150` makes Lumen's "could not match" reply list raw column names ("cash_usd, net_worth_usd"). The user sees column names instead of plain words.
- `ui/src/v1/cxui/ProjectPage.tsx:~106` shows the raw gold table names in the Gold tables drawer, with column types. I assert on them because the planted fact names them, but they are table names and types on screen.
- Today (`ui/src/v1/e5/TodayPage.tsx`) files the "shared with you" card under "Worth a look", not "Needs me". A sponsor may not expect a shared dashboard there, so I assert it there.
- `ui/src/v1/cxui/DashboardView.tsx:15` gives one error for "not shared" and "no longer exists", with no way back or next step. That falls short of the ui-copy rule that errors say what to do next.
---

## After UX round 1 (orchestrator, 9 Oct): labels changed, journeys must follow
- Intent: "Hand to the architect" is now "Sign the intent of work"; SOP buttons are "Download the procedure" / "Read the procedure here" (uc10a_1.py:184-190, uc9a_2.py:72-115).
- Today: "Dismiss" is now the link "Not for me".
- Build: "Download the Airflow file" sits under an engineers' section; SQL under "How it is calculated"; document 3 is "Tables".
- Consume: links to Office view, CIO Brief, Managers, Benchmark now exist on the Consume landing; "Gold tables" is "Figures available".
- Bar labels are sentence case (Intent, Action, Build, Consume, Map).
