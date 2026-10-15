# Team of ten: results (15 Oct, synthetic Evergreen Office, local)

Each person: own fresh office, said their need in their own words, dropped their files, made the three decisions, then asked
their dashboard question; the answer was checked against the answer key. Runner: docs/test/uc-live/uc6-scripts/v3_persona.py.

| # | Person | Build | Reached | Dashboard answer | Verdict |
|---|---|---|---|---|---|
| 1 | Daniel Foo, Head of Finance | Can each entity meet its capital calls (UC6) | Live | July cash by entity exact to the cent | **Done** |
| 2 | Anita Rao, Head of Data | Pipeline and insight (UC10) | Live | "no holdings records in the ready table" | Live, no figure |
| 3 | Raj Patel, CIO | Why NAV moved (UC1) | Live | no figure | Live, no figure |
| 4 | Mei Chen, Principal | Morning net-worth note | Live | "ready tables show zero rows" | Live, no figure |
| 5 | Grace Ong, Operations Lead | Break desk (UC2) | Live | break listed, amount missing | Live, figure missing |
| 6 | Sofia Reyes, Investment Analyst | Manager diligence (UC7) | Decision 1 | - | Blocked: may not sign; Harbor left her stuck |
| 7 | Tom Hale, Risk and Compliance | Limits (UC5) | Decision 1 | - | Blocked: may not sign; Harbor left him stuck |
| 8 | Helen Foo, Fund Accountant | Statements expected vs received (UC3) | Loading | - | Blocked: inputs are PDFs |
| 9 | Sam Lee, Operations Clerk | Trades vs administrator (UC8) | Loading | - | Blocked: confirmations are PDFs |
| 10 | Priya Nair, Office and HR | Process map and SOP (UC9) | Loading | - | Blocked: input is a written process, not data |

Fixed during the test (in code, pushed): confirming a brief accepts its suggested figures and records "no earlier figures";
a file that will not load is set aside and the build goes on; the fast cash answer only takes cash and calls questions and never
shows zeros; the test runner retries a dropped poll. Also seen: the server drops some requests while Harbor drafts.

## What to build next (by people unblocked)
1. **The build fills the brief's figures** (5 people: Anita, Raj, Mei, Grace, and the rest once unblocked): the design and SQL
   for each figure in the brief, checked against the answer key before go-live. Today only cash and calls are filled.
2. **Harbor reads PDFs** (Helen, Sam): statements, notices and confirmations through the document reader, marking fields once.
3. **Route the brief to someone who may sign** (Sofia, Tom): a person who may not sign sends Decision 1 to the signer in Action.
4. **Process-only builds** (Priya): a written process becomes a process map and SOP, with no data load.
