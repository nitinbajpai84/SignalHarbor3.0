# Build flow V6 (Nitin, 11 Oct 2026)

One agent family, two roles: **Span the architect** designs the target and gets everything ready; **Span the builder** executes, tests against a benchmark and goes live. They talk to each other; people approve at two points. Lumen then proposes a ready dashboard from the intent.

## Step 1 · Intent (North) — unchanged
Signed intent of work + process map. It already tells us: the figures wanted (KPIs), who reads them, how often, the steps today, the systems and files named, structured or not.

## Rule: never ask twice
The system mapping captured in the intent (each system or file: what it holds, owner, format, how it arrives, how often) is carried forward. North asks "how does it arrive and how often" during the intent when a system is named, so the architect starts with it. The architect shows each system "from the intent" for the builder to **confirm**, never to re-enter; it asks only for what the intent did not capture. The builder confirms each connection against the same record; a mismatch (different file name, columns, host) is raised once, with the intent's value beside it, and the corrected value updates the intent's system map and the design pack together.

## Step 2 · Architecture (Span, architect) — "design the target, get the builder ready"
**2a. Read before asking.** From the signed intent and process map Span lists: the source systems named (structured: Excel, CSV, database, admin export; unstructured: PDF statements, emails), what is already connected (connectors, landed files, the catalogue), and the figures to produce. It scans connected systems and landed files itself.

**2b. Ask only what is missing (the minimal question set).** Span asks a question only when the intent and the scans cannot answer it, at most one screen, each with a proposed default to accept:
1. **Sources:** for each source not yet connected: how does it arrive (upload a sample / mailbox / SFTP / SharePoint / database)? A sample file is requested only for a source never seen, or a PDF whose fields must be read (mark the fields on the sample).
2. **Grain and keys:** the level of each figure (per fund, per entity, per day or month) when the intent is ambiguous.
3. **History:** which attributes must keep their history (slowly changing, type 2: e.g. manager, asset class, portfolio owner); default: none beyond values by date.
4. **Checks:** which controls must hold (control totals vs source footer, two sources agree within a tolerance, completeness by a deadline); defaults proposed from the process map.
5. **Definitions:** formulas for each KPI not already signed (e.g. return, net worth); the signed definition is used where it exists.
6. **Freshness:** when the data must be ready (e.g. 06:00 daily, 5th business day monthly); default from the intent's "when needed".
7. **Access:** inherited from the intent; asked only if a table needs narrower access.

**2c. The design pack** (one document, versioned, editable by the team; each section correctable like the intent):
- **Target model:** silver tables used or extended from the company model; gold tables with columns, types, definitions, grain, keys, history (type 2 columns), owners.
- **Data catalogue:** every table and column with meaning, source, sensitivity.
- **ETL mapping sheet:** source field → bronze → silver → gold, with transformations and formulas.
- **Rules of implementation:** checks and tolerances, history handling, refresh schedule, late-data handling, the benchmark to test against.
- **Sources and connections:** each source with how it arrives and its sample.

**2d. Approve.** The head of data (or the project's data lead) approves the pack. Approved means locked for the builder; still editable through a new version.

## Step 3 · Pipelines (Span, builder) — "execute, test, go live"
1. **Connect** each source exactly as the pack says (connectors, uploads, PDF reading with fields marked). The builder goes back to people only when a connection fails or a sample is needed.
2. **Build and run automatically** (lean team): Span generates the pipeline from the mapping sheet and runs it on a copy without waiting for a click.
3. **Ask for a benchmark:** "Do you have last month's report or figures I should check against?" The person uploads it (or picks a signed one).
4. **Show the result:** tables built, rows, checks, the key figures, and the **variance against the benchmark**, line by line.
5. **Decide:** looks good → **Go live** (schedule from the pack). Variance → Span the builder hands it back to Span the architect with the evidence; the architect updates the pack (new version, the change shown), the builder reruns. People see the conversation between the two roles.

## Step 4 · Dashboards (Lumen) — "ready on arrival"
When the pipeline goes live, Lumen proposes a **starter dashboard** from the intent's KPIs, readers and decisions: the key figures, their trend, the breakdowns named in the intent, and the checks status. The person accepts it, or asks for specific additions; nothing has to be built from scratch. Then approval and delivery as today.

## What already exists and is reused
Connectors (W2), profiling and mapping sheet (Scan, Mapping rooms), PDF reading and figure confirmation (evidence queue), plan versions and approval (b6), sandbox and live runs (b6_run), verify and review (b9), agent handoffs (W3), studio and Lumen (DS1/OP1).
