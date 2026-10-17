# Four test cycles: the ten Evergreen people (15-16 Oct, synthetic data, local)

Each cycle builds a fresh office for each person. The person says their need, drops their files, and makes the three decisions. Then they ask
their dashboard question, and the answer is checked against the answer key in `packs/family_office/1/role_builds.yaml`.
Reports and screenshots are in `D:/Temp/sh3-cycles/c1..c4`. The runner is `docs/test/uc-live/uc6-scripts/v3_persona.py`.

| Person | Before | Cycle 1 | Cycle 2 | Cycle 3 | Cycle 4 |
|---|---|---|---|---|---|
| Daniel Foo, Head of Finance | ✅ | ✅ | ✅ | ✅ | ✅ |
| Priya Nair, Office and HR | stuck | ✅ | stuck (regression) | ✅ | ✅ |
| Raj Patel, CIO | no figure | no figure | stuck | honest "not yet" | ✅ original 10,000,000, amended 10,180,000, change +180,000 |
| Sofia Reyes, Investment Analyst | stuck (may not sign) | stuck | wrong answer | honest "not yet" | ✅ 7,012,500 |
| Anita Rao, Head of Data | no figure | ✅ | no figure (regression) | ✅ | no figure (design varies run to run) |
| Mei Chen, Principal | no figure | stuck | no figure | **wrong figure 44,000,000** | stuck: model SQL error |
| Grace Ong, Operations Lead | figure missing | wrong figure, repeated | stuck: bad SQL | honest "not yet" | stuck: no starter dashboard |
| Tom Hale, Risk and Compliance | stuck (may not sign) | stuck | no figure | no figure | no figure |
| Helen Foo, Fund Accountant | stuck (PDFs) | stuck | stuck | chatty reply | figure 6, key says 63 |
| Sam Lee, Operations Clerk | stuck (PDFs) | no figure | no figure | honest "not yet" | stuck: no starter dashboard |
| **Correct answers** | **1** | **3** | **1** | **3** | **4** |

## What was built and fixed across the cycles
- **Sign-off.** A person who may not sign sends Decision 1 to the signer. The signer's Confirm fills the gaps and signs in the signer's name, and the record shows both people.
- **Process-only builds.** A written process becomes a process map and an SOP, with no data load.
- **Figures.**
  - Each figure in a brief gets a ready table, and Decision 3 shows its row count.
  - A design that joins every entity to the whole company is refused, and so is a table that reads only empty tables.
- **Documents.**
  - PDFs are read with one question per new layout. Emails, notes and letters are read as documents.
  - A figure in a document loads only after the person confirms the quoted line.
  - Amended values are linked to the earlier value they replace.
- **Loads.**
  - FX rates, labelled report workbooks, and bank statements (the Transactions sheet, with Debit and Credit columns) now load.
  - A file that will not load is set aside with a reason, and the rest of the build goes on.
- **Honest answers.** A figure question gets numbers from rows, or one "Not available yet" line that names what is missing.
  - A currency is never read as a name, and figures in different currencies are never added together.
  - A partial total says what it covers.
- **Bad SQL.** Each design is run once against an empty copy of the tables before the trial run.
- **Tests.** 163 v3 tests pass together.

## What repeats and is still open
1. **Model designs vary from run to run.** Anita passed in cycles 1 and 3 and failed in cycles 2 and 4. Mei's and Grace's designs also change between runs. The next step is to keep a design that worked, as a skill for that kind of figure, and reuse it instead of redesigning each time.
2. **Wrong figures are still possible in two places:**
   - "Net worth" can be built on commitments;
   - Grace's break can be shown as a plain sum (-44,400).
   Both need a rule saying which tables a figure may read.
3. **"No figures to build a starter dashboard"** stops Grace and Sam at go-live. This is new in cycle 4 and needs a look.
4. **Waiting on Nitin:**
   - an FX confirmations table (Sam);
   - an expected statements table (Helen);
   - whether report figures need a home of their own (Mei);
   - keeping the raiser-accepts-drafts permission;
   - the cash sign convention (money in positive);
   - picking a report total by its "Total" label.

# Rounds 5 to 8 (16-17 Oct): recipes, binding by meaning, guards

| Person | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 |
|---|---|---|---|---|---|---|---|---|
| Daniel Foo, Head of Finance | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | stuck | ✅ |
| Anita Rao, Head of Data | ✅ | ✗ | ✅ | ✗ | ✅ | ✅ | ✅ | ✅ |
| Raj Patel, CIO | ✗ | stuck | ✗ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Mei Chen, Principal | stuck | ✗ | wrong | stuck | ✅ | ✅ | ✅ | ✅ |
| Grace Ong, Operations Lead | wrong | stuck | ✗ | stuck | ✅ | wrong | ✅ | ✅ |
| Sofia Reyes, Investment Analyst | stuck | ✗ | ✗ | ✅ | ✅ | ✅ | ✅ | stuck (12 mapping rows) |
| Tom Hale, Risk and Compliance | stuck | ✗ | ✗ | ✗ | ✗ | ✅ | stuck | ✅ |
| Helen Foo, Fund Accountant | stuck | stuck | ✗ | ✗ | ✅ | ✅ | ✅ | ✅ |
| Sam Lee, Operations Clerk | ✗ | ✗ | ✗ | stuck | stuck | ✗ | stuck | ✅ |
| Priya Nair, Office and HR | ✅ | stuck | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Correct** | **3** | **1** | **3** | **4** | **8** | **8** | **7** | **9** |

Round 8 note: Sam's run log ends "DONE ops_clerk: live; check PASS". His saved report was overwritten afterwards by a parallel
Step 2 test that restored an older backup of the same shared file. The runner keeps its state in shared files; give each run its own.

# Rounds 9 and 10 (17 Oct): merged version (figure records, two-model judge, trust screens, UI audit fixes)

| Round | Correct | Questions to the person | Note |
|---|---|---|---|
| 9 | 9 of 10 | 0 for all nine | Anita's start failed: a reader caught the thread file mid-write (HTTP 500); fixed by saving to a side file and swapping it in |
| 10 | **10 of 10** | **0 for all ten** | Every person live, every answer matches the answer key |
