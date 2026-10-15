# Signal Harbor 3.0: UAT guide (test one use case end to end, as a real user)

You play **Anita Rao, head of data at Evergreen Office** (a synthetic family office). You bring one question, give Harbor your files, make
three decisions, and check that the numbers are right. Then you drop next month's files and check that only exceptions reach you.

Plan about **75 minutes** for one use case (most of it is Harbor working; you can keep the page open and come back).

---

## 0. Before you start (all prepared for you)

| What | Where |
|---|---|
| The app (local, this machine only) | http://127.0.0.1:8630 |
| Your sign-in | `anita.rao.evergreen@example.test`; the password is in `D:/Temp/sh3-uat/_control/seed_credentials.txt` |
| Your test files (copies, safe to use) | `D:/SH3-UAT-files/` with one folder per month: `2026-07`, `2026-08`, `2026-09`, `2026-10` |
| Harbor's drop folder (optional way in) | `D:/Temp/sh3-uat/evergreen/dropbox/` |
| The right answers (answer key) | `docs/demo/uc6/ANSWER-KEY.md`, summary in section 6 below |
| Your defect log | section 7 of this guide (copy the table into a sheet) |

The office is fresh: 3 entities (Evergreen Holdings EG-HOLD, Evergreen Family Trust EG-TRUST, Entity B EG-B), 5 fund commitments,
no transactions, no threads. "Today" for the office is **31 July 2026**.

If the app does not open: in a terminal in the `Signal Harbor 3.0` folder run
`python tools/serve_test.py --port 8630 --data-root D:/Temp/sh3-uat --scheduler` and wait for "serving".

---

## 1. Pick your use case

Choose **one**. It must be answerable from the files in `D:/SH3-UAT-files/`:

| Files you have (each month) | What is in them |
|---|---|
| `bank_cash_EG-HOLD_…csv`, `bank_cash_EG-TRUST_…csv`, `bank_cash_EG-B_…csv` | Daily bank balances and movements per entity (opening, net movement, closing, narrative) |
| `administrator_cash_….csv` | The administrator's daily closing cash per entity: the independent figure to check against |
| `commitments_schedule_….xlsx` | Each fund commitment: committed, called to date, uncalled, the manager's call plan |
| `notice_receipt_log.csv` and the `.pdf` notices | Capital call and distribution notices: fund, amount, due date, when received |

**Recommended (has a full answer key):** "Can each entity meet its capital calls from cash?" (cash by entity, calls due in 30 and 60 days,
uncalled commitments).
**Your own:** anything else these files can answer, for example "How much uncalled commitment do we have by fund?" or "Which bank movements
are not explained?". For your own question you check the numbers yourself against the files.

Write your question down before you start, in one or two sentences, the way you would say it to a colleague. Include **who reads it**
(for example Mei and Daniel), **who decides** (you) and **how often** (monthly).

---

## 2. The test, step by step

Tick each check. Anything that does not happen as described is a defect: log it in section 7 with the step number.

### Step 1. Sign in and look around (5 min)
1. Open http://127.0.0.1:8630 and sign in as Anita.
   - [ ] You land on the **Desk** (top bar: Desk · Threads · Board · Files · Trust). It says "Nothing here yet".
2. Click **Set up the office**.
   - [ ] The setup page shows the steps of day one, with your industry (Family office) and what is done.
3. Click **Trust**, then each tab: Ontology, Industry model, Language, People, Runs and proof, Workbench, Connections.
   - [ ] Every tab opens without an error. Industry model shows the family-office objects (Entity, Account, Fund, Commitment …).
   - [ ] People lists the office's people with Decides / Does / Reads.

### Step 2. Bring the July files (5 min)
1. Click **Files**. Drag all the files from `D:/SH3-UAT-files/2026-07/` onto the drop zone
   (or copy them into the drop folder `D:/Temp/sh3-uat/evergreen/dropbox/`).
   - [ ] Each file shows a progress bar, then appears in the list.
   - [ ] Files are listed as "waiting" for now. That is expected: no question has been asked yet.

### Step 3. Ask your question (5 to 8 min, mostly waiting)
1. Go to **http://127.0.0.1:8630/v3/start** (the empty Desk does not have a box yet). Type your question in your own words. Click **Send to Harbor**.
   - [ ] The page waits while Harbor drafts the brief. **This takes 3 to 5 minutes** (known, see section 8). Do not press Send twice.
   - [ ] You land on your **thread**: your message, Harbor's reply, and on the right **Decision 1 · Is this what you want?**

### Step 4. Decision 1: the brief (5 min)
Read the brief card: the question, the files needed, who reads it, refresh, when a case is raised.
- [ ] It says what you asked, in your terms. Suggested lines (usual practice) are marked as suggestions.
- [ ] If Harbor writes "Before you confirm, I still need: …", answer in the box at the bottom in plain words (or say "use the usual practice"). It should then let you confirm.
- [ ] If something is wrong, say it in the box (for example "Daniel decides, not me") and check the brief changes.
1. Click **Confirm**.
   - [ ] Harbor says it is working. Progress chips appear one by one: Signed the intent, Handed over to build, Read the systems, Read the sample files, Drafted and approved the design pack, Read the dropped files.
   - [ ] **Nothing is asked of you** during this. It takes **5 to 10 minutes**. You can go to the Desk and come back.
   - [ ] On the Desk, the thread shows as working; Files now shows your July files as recognised and linked to your thread.

### Step 5. Decision 2: Harbor's understanding of your files (5 min)
The panel shows each file, what Harbor read it as, where it goes (reused or new), and a confidence label. Then a few questions.
- [ ] Each of your files is listed. None is missing. The wording is plain (no table names like `cash_movements`).
- [ ] Questions are only about real doubts (low confidence), plus **"Which file should I check the numbers against?"**
1. For the check question pick **administrator_cash_2026-07.csv** (it comes from someone else, so it is an independent check).
2. Answer any other question, then click **This is right, carry on**.
   - [ ] Chips: Applied your answers, Accepted the mappings and loaded, Ran on a copy, Compared with the report. About **3 to 6 minutes**.

### Step 6. Decision 3: do the numbers match? (10 min, the most important step)
The card lists each figure Harbor checked: Harbor's number, the check file's number, and whether they match.
- [ ] Compare with the answer key (section 6). **Write down every figure** Harbor shows and the expected figure.
- [ ] A difference is explained, or clearly marked as not matching. Harbor never says "numbers match" when they do not.
- [ ] Any source Harbor left out (no file arrived) is named in the summary.
1. Decide as a real head of data would: if the numbers are right, click **Go live**; if not, click **Not yet** and log why.
   - [ ] After Go live: chips Went live, Built the starter board, Wrote the morning note. Harbor says it is live.

### Step 7. What the readers get (10 min)
1. **Board**: [ ] shows the figures of your question (for UC6: cash by entity, calls due, uncalled), not generic tiles. Hover a number: where it is from.
2. **Board → Ask about this board**: ask "Which entity has the least cash?" [ ] The answer names the entity and cites a source.
3. **Note** (http://127.0.0.1:8630/v3/note): [ ] the morning note has a headline and the figures, matching Decision 3.
4. **Ask** (http://127.0.0.1:8630/v3/ask): ask your question in different words (for example "dry powder by fund"). [ ] It understands, or says plainly it cannot.
5. **Trust → Runs and proof**: [ ] your copy run and live run are listed with their checks.
6. **Trust → Workbench** for your thread: [ ] every step Harbor took is listed, with raw / clean / ready tables.

### Step 8. The next month: only exceptions (15 min)
1. Drop all files from `D:/SH3-UAT-files/2026-08/` into Files (or the drop folder).
   - [ ] Files are recognised for your thread **without any question to you**.
   - [ ] Within a few minutes Harbor runs by itself. You did not have to press anything.
2. Go to the **Desk**.
   - [ ] Only things that need you appear (for example a late notice or a file it could not read), each with a plain reason and one-click actions.
   - [ ] If nothing needs you, the Desk says so, and the Board and Note show August figures (check them against the key).
3. Optional: repeat with `2026-09` (an amended call notice) and `2026-10` (Entity B cannot cover all its calls: there should be a shortfall exception).

### Step 9. Your verdict (5 min)
Answer these in your log:
1. How many times did you have to act? (Target: one message, three decisions, then only exceptions.)
2. Was there any moment you did not know what to do next?
3. Did you trust the numbers? Why or why not?
4. Would Mei (who never sees the build) understand the Board and the Note on her own?

---

## 3. What "pass" means

| Area | Pass when |
|---|---|
| Effort | You typed one message and clicked three decisions; nothing else was asked unless a file was really unclear |
| Honesty | Every figure is traceable; a mismatch is shown as a mismatch; nothing is invented |
| Numbers | July and August figures match the answer key to the cent |
| Monthly | August ran by itself and only exceptions reached the Desk |
| Words | No technical terms in front of you (no table names, "bronze/silver/gold", agent names) |

---

## 4. If something gets stuck

| You see | Do this |
|---|---|
| A **question card** in the thread ("I could not …") | Read it, answer in the box at the bottom, or type `retry`. Log it as a defect either way. |
| The page keeps waiting more than 10 minutes | Refresh the page. The thread keeps its state. Log the time. |
| A page shows an error | Refresh once. If it stays, log the page and the message. |

---

## 5. Start again from a clean office

Stop the server (close its terminal), then in `Signal Harbor 3.0/docs/test/uc-live/uc6-scripts` run
`python make_clean_env.py --root D:/Temp/sh3-uat2 --today 2026-07-31`
and start the server with `--data-root D:/Temp/sh3-uat2`. Your earlier office stays untouched in `D:/Temp/sh3-uat`.

---

## 6. Answer key (recommended use case, USD)

**July (as at 31 Jul)**

| Entity | Cash | Calls due within 30 days | Calls 31 to 60 days |
|---|---|---|---|
| Evergreen Holdings (EG-HOLD) | 2,305,906.48 | none | none |
| Evergreen Family Trust (EG-TRUST) | 1,252,492.34 | none | none |
| Entity B (EG-B) | 905,000.00 | none | none |

Commitments: committed 44,000,000.00; called 30,550,000.00; **uncalled 13,450,000.00**.
By fund (uncalled): A 3,750,000 · B 800,000 · C 2,400,000 · D 500,000 · E 6,000,000.

**August (as at 31 Aug)**: EG-HOLD 2,287,630.12 · EG-TRUST 1,199,690.58 · EG-B 654,014.07. No calls due. Uncalled unchanged.
Traps to watch: a Cedarpoint call notice (300,000) arrived on 12 Aug for a call already **paid on 23 Jul** (must not show as an open call);
a 221,872.96 sweep out of EG-B on 14 Aug is a treasury transfer, **not** a call.

**September and October**: see `docs/demo/uc6/ANSWER-KEY.md` sections 3.3 and 3.4 (amended notice; Entity B shortfall of -169,600.00 after all noticed calls in October).

---

## 7. Defect log (copy into a sheet)

| # | Step | What you did | What you expected | What happened | Severity (blocks / wrong number / confusing / cosmetic) | Screenshot |
|---|---|---|---|---|---|---|
| 1 | | | | | | |

---

## 8. Known issues before you start (so you do not lose time on them)

1. **Slow steps.** Drafting the brief and the design each take 2 to 5 minutes; the page waits. Pages may also be slow while Harbor works.
2. **The design may not cover every figure in your brief.** In the last run the design built holdings and net worth tables instead of
   cash by entity and calls due, so Decision 3 showed "this run has no figure" for each check and the Board had no liquidity tiles.
   If you see this, log it, it is the main open defect.
3. **The morning note** takes its figures from the office liquidity view, not yet from your thread's own tables.
4. Not built yet: answering "What is this file?" on the Files page, expected-vs-arrived dates, duplicate detection.
5. Harbor's wording of the brief varies from run to run; in 1 of 4 runs it asked one extra question before Decision 1.
