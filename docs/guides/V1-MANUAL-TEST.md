# Signal Harbor 1.0: the manual walk (7 October 2026, evening build)

One journey, one company, three sign-ins. Everything below is on **http://localhost:8400**. Sign-ins and passwords: `data/_control/seed_credentials.txt` in this repo (two spaces between email and password; the 2.0 file is different).

| Who | Sign-in | Seats |
|---|---|---|
| Arjun Mehta | `arjun.mehta.neera@example.test` | Decision maker (and, as company admin, every other seat too) |
| Leela Raman | `leela.raman.neera@example.test` | Architect, data engineer, ops manager |
| Dev Sharma | `dev.sharma.neera@example.test` | Consumer only |
| Fresh Owner | `nitin.fresh@example.test` | Decision maker of Fresh Harbour, an empty company |

Neera already has the 20 landing files (`data/neera/landing/<folder>/`) and 20 documents (`data/neera/documents/`), so you can walk the whole journey without preparing anything. To start the journey again from nothing: `python tools/reset_v1.py neera` (removes the intents, build records and the marts Flow built; keeps the files and documents).

Clicks are counted from the page named in the step; "type" is not a click. Reading time is yours. Agent time is what the agents take on their own (the model answers in 10 to 40 seconds a turn).

## Part 1. Arjun, decision maker: from one line to a signed intent of work (about 15 minutes, of which 8 waiting on North)

| # | Where | You do | The agent does | Clicks | Value |
|---|---|---|---|---|---|
| 1 | Sign in → Home | Read "What waits for you, Arjun": seat chips, "Start an intent", nothing waiting yet | | 1 (sign in) | One page says what needs you; nothing else to hunt for |
| 2 | Intent Centre (top bar) → company page | Read the four sections: who we are, systems, policies, documents (the 20 files). Add one policy (kind: retention, "Keep seven years"), Save | North reads this page before every reply ("North has read this" line shows the time) | 3 (bar, add, save) | The company's own words and rules reach the agent once, never retyped |
| 3 | Home → Start an intent | Type one line: *I have to run the monthly performance report for the family*. Start | North opens the thread, asks the first of six needs (goal and why) | 2 | No form: a sentence starts the work |
| 4 | Thread | Answer North in your own words, six to eight turns (goal, process today, inputs, KPIs, rules, unclear). Say "the samples are already in the landing folder". Watch the right column fill: goal, process, KPIs, sources, governance, unclear | North asks one question per need and at most one follow-up; drafts the intent of work after every turn; reads the landing folders and the documents into the catalogue when the thread is ready; never guesses, writes an unclear point instead | 6 to 8 (Send) | 8 minutes of conversation produce the whole brief; a Ardmore-style start took six screens and a wall |
| 5 | Thread → "Read and sign" | Read the eight sections. Edit one KPI definition in place. Settle one unclear point (the 10 % vs 12 % concentration limit: "the policy is right"); leave the others | The catalogue shows the landing tables (one per folder, a `_v2` where columns changed mid-year), the document sources with what was read from each, and a gold table per KPI that has a source | 3 (open, edit, save) + 2 (settle) | The catalogue covers files *and* documents, each fact with the file it came from |
| 6 | Intent of work → Sign → "Yes, I sign" | Sign | The record freezes; definitions go to the glossary and tables to a signed catalogue; North hands over to Span in the room | 2 | One signature, one document, downloadable (Markdown) |
| 7 | Intent → room | Read the agents' conversation: North's hand-over, Nira's "waiting on Span since …" | Nira works out the stage from the records and nudges whoever is next | 1 | You see who is waiting on whom without asking anyone |

Also try: Download → Markdown (1 click); the Map (top bar) shows this intent → its problem → sources → KPIs → tables (1 click).

## Part 2. Leela, architect: design, scan, mapping sheet (about 5 minutes, 2 waiting on Span)

| # | Where | You do | The agent does | Clicks | Value |
|---|---|---|---|---|---|
| 8 | Sign in → Home | Read the architect cards: "Review the design", then "Agree the scope" waits for Arjun | | 1 | |
| 9 | Build → design | "Ask Span for the design" | Span drafts landing, cleaned and report layers per KPI from the signed intent of work; the diagram shows sources → tables → KPIs; a note says what it assumed | 2 | A three-layer design in a minute, from the brief, not from a blank page |
| 10 | Build → scan | "Run the scan" | Span reads every landing file and sheet and says per KPI: available, partly (which field is missing, in which file), not available | 1 | You know before building what the files can and cannot answer |
| 11 | Arjun: scan → Agree | Sign in as Arjun (or stay as Arjun in another tab). Tick the KPIs to build, "Agree N KPIs" | The scope is recorded; Span hands over to Flow in the room | 2 | One click fixes the scope; nobody builds what the data cannot support |
| 12 | Leela: Build → mapping | "Ask Span to draft" | Span writes one row per target field: source, field, transformation (sum / latest / a formula written out), rule, test. A formula the built-in runner cannot express stays **unclear** for the engineer, never guessed | 1 | The ETL mapping sheet a data engineer expects, downloadable as .xlsx (1 more click) |
| 13 | mapping | Filter Unclear; Edit one row, Save row | | 3 | Human corrections stick through redrafts |

## Part 3. Leela, data engineer and ops manager: load and confirm (about 3 minutes, 1 waiting on Flow)

| # | Where | You do | The agent does | Clicks | Value |
|---|---|---|---|---|---|
| 14 | Build → runs | "Run the load" | Flow turns the mapped rows into one pipeline per source folder, loads bronze → silver, runs the checks, builds the gold marts it can (sum / latest per period), logs every run with its note; a missing file or failed check goes to the room | 1 | Every figure later shown traces to a run here |
| 15 | Build → ops (top bar: Build Centre) | For each source: Loaded for 2026-09, or Not loaded with a reason | The Watcher alerts late sources; each act is posted to the room | 1 per source | The ops manager's word is the gate: nothing is consumed until a period is confirmed |

## Part 4. Consume (Dev, then Arjun) (about 2 minutes)

| # | Where | You do | The agent does | Clicks | Value |
|---|---|---|---|---|---|
| 16 | Sign in as Dev → Consume Centre | Read the cards: value, month, trend for KPIs whose period is loaded; "Not available yet" with the scan's reason or the ops note for the rest. Click a value: the run and the rows behind it | | 1 + 1 | No number without its run; nothing shown that was not loaded |
| 17 | Arjun → Consume → offers | Read "FX rates feed: with it you would also get …". Click "We have it" on one | The intent of work reopens at version 2 with the new source and an unclear line; North is told in the room; the previous signature is kept in the history | 1 | The next step is a decision, not a project |
| 18 | Home (any seat) | Read what now waits: Arjun has an intent of work to re-sign | Nira has moved the stage back to the thread | 1 | The loop closes where it started |

## Fresh Harbour (you, from nothing)

Sign in as Nitin: Home says nothing waits. Company page: fill who we are, add two systems and one policy, drop a document (a .md file). Start an intent with one line; North reads the empty company and asks everything. Drop a CSV into the thread: it appears as a source with its columns. Nothing crashes on an empty company; what is missing is said in words.

## Known rough edges (8 October, 00:40)

- North sometimes repeats a question in its follow-up (one need asked three times in one walk); answer again or type "nothing more".
- A gold value that is a formula: Flow asks the model for one SELECT over the KPI's silver tables, checks it (one SELECT, only those tables, no file or network functions, columns period and value) and runs it; the SQL sits on the mapping row for the engineer. On the demo company this built single-issuer concentration and the fee ratio; time-weighted return, money-weighted return and the benchmark-relative figures were declined with a reason (the definitions give no formula and the tables carry no signed cash flows). Those stay "Not built yet" until the engineer writes the SQL on the row.
- Signing takes about a minute and a half on Neera: North reads all 20 documents through the model at that moment.
- Word export of the intent of work needs the python-docx package; Markdown works.
- The ops page lists only sources an intent of work names; the 2.0 demo sources are hidden.
