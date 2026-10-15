# Build Centre: specification (6 Oct 2026, first draft)

Status: proposal for Nitin's review, written from his answers of 6 Oct (DuckDB in the company plane; pipelines driven by contracts and SLAs; a scheduler with dependencies; step by step from an environment check to a Watcher that posts daily feeds). The flow follows the module 4 proposal diagram `docs/architecture/sh-m4-build.json`: Signed inputs → Environment check → Estate scanner → Architect agent → Blueprint sign-off → Build agents → Warehouse → Prover → Release sign-off → Watcher. Companion specs: `INTENT-CENTRE-SPEC.md`, `COMPANY-GRAPH-SPEC.md`.

## 1. What the Build centre is for

It turns the signed gap report and the governed catalogue into working data: a warehouse in the company's plane, pipelines that load it on a schedule with SLAs, every measure reconciled to the figure the company already reports, and a Watcher that tells owners when something is late or wrong. The customer gives nothing new except five environment answers, read-only access to an existing warehouse if there is one, and two signatures.

Three rooms, in the order the customer meets them:

| Room | Steps | Agent | Signature |
|---|---|---|---|
| Architect your design | environment check, estate scan (skipped when there is no existing warehouse), blueprint | Architect | blueprint: head of data, and IT where IT owns the infrastructure |
| Build the data | build (bronze, silver, gold into DuckDB), SLA and contract checks, prove each measure against the reported figure | Builder, Prover | release: sponsor |
| Ops manager | schedule, freshness, drift, anomalies, daily feed to the owners | Watcher | quarterly owner review |

## 2. Inputs, all already signed

- The phased plan (which sources in which band) and the accepted risks: `m3_connect` plan outcome.
- The governed catalogue: per measure the source, fields, calculation, period, currency, owners, classification, who may see, and the quality rules from the scan (IC-0d).
- The profile: systems, how data lands, frequency, arrivals log, constraints (licences, internet, deadlines).
- The company graph for lineage and impact (CG-1).

## 3. Room 1: Architect your design

### 3.1 Environment check
Five questions, prefilled from the profile and the constraints file, confirmed by the head of data in one screen:
1. Where may the warehouse live? (default: inside this company's plane, on this machine; alternatives: the customer's cloud account, an existing warehouse)
2. Is there a warehouse or lake today? (name, kind, read-only access or none)
3. Is there a scheduler today? (none; a cron; Airflow; something else)
4. Where do files arrive? (a folder, a mailbox, a portal export, an API)
5. Where should alerts go? (a channel webhook, email, the screen only)

Output: an environment record in the plane with provenance. The answer to 2 decides whether the estate scan runs.

### 3.2 Estate scan (only when a warehouse exists)
Read-only metadata: schemas, tables, columns, row counts, last-updated. For each catalogue measure the scanner proposes one of three paths: **adopt** (map the definition onto existing tables, build nothing), **improve** (fill a gap in an existing table), **build** (no fit). Output: a fit report per measure, with the evidence (table, column, sample counts). Nothing is read row by row except counts.

### 3.3 Blueprint
The Architect agent writes `warehouse/blueprint.json` in the plane:
- `model`: facts and dimensions derived from the catalogue (grain, keys, measures, slowly changing attributes where the catalogue says a value changes), for the current plan band only.
- `lineage`: for each measure, source → fields → transformations → mart column, from the catalogue's technical definition; where a system table is known from the estate scan or the data dictionary, it is named.
- `rules`: the quality rules from the scan and the matching rules from the trial, as checks with a severity (block the load, warn, inform).
- `access`: from the governed state: who may see each mart and column; restricted measures become separate marts readable only by their list.
- `schedule`: per source, the expected arrival (from the arrivals log and the systems list), the SLA (from the deadlines file: for example, the committee pack needs the marts by working day 8), dependencies between sources and marts.
- `infra`: where things run, from the environment check.

Two diagrams are drawn from the JSON, never by hand: the infrastructure and data-flow picture as an Archify architecture spec (we already render and validate these), and the lineage per measure as the company graph's Trace view. The Python `diagrams` library is an option for cloud-provider icons when a customer deploys to a cloud account; it needs Graphviz installed, so it is a later package, not the default.

The blueprint screen shows the model, the three-path fit per measure, the rules, the access list and the schedule, each with its source. The head of data (and IT where named) signs. Signed means read-only; a later band produces a new blueprint version beside it.

## 4. Room 2: Build the data

### 4.1 Where the warehouse lives
One DuckDB file per company, `warehouse/company.duckdb`, inside the plane (A-064). Reasons: zero infrastructure, fits data locality, handles the volumes a mid-size business produces for years, and is a file a person can back up and inspect. Layers inside it: `bronze` (as-landed rows, one table per source file type), `silver` (typed, deduplicated, conformed), `gold` (the marts the catalogue defines). People who want to query it use a read-only query screen in the product or any SQL client that speaks DuckDB (DBeaver and the like) against a **read-only copy** the Watcher refreshes after each load; the live file is never opened by a client tool. Restricted marts are written to a separate file readable only by the people on the list; DuckDB has no row-level security, so separation is by file (A-065).

A customer with an existing cloud warehouse chooses it in the environment check; the same blueprint compiles to that dialect (the earlier repo's `sql_dialect.py` on sqlglot) and the push follows the cloud-push rule: two named approvers, synthetic data in a pilot.

### 4.2 Pipelines are contracts first, code second
Every source gets a **pipeline contract**, `warehouse/pipelines/<source>.yaml`: where it lands, the file pattern, expected arrival and SLA, the schema it must match, the quality rules to run and what to do when one fails, the dependencies (which marts wait on it), and the owner to tell. The Builder agent generates the code from the contract and the blueprint: bronze load, silver transform, gold marts, and the tests. The contract is what the customer reads and what the Watcher enforces; the code is derived.

Scheduling (A-066). The contracts need a scheduler with dependencies. Two runners, same contracts:
- **The built-in runner** for a plane installed on one machine: a small in-process scheduler (arrivals watched, dependencies resolved, retries, a run log), no extra services. This is the default and what the demo uses.
- **An Airflow DAG per company**, generated from the same contracts, for customers who already run Airflow or ask for it. Airflow is heavy to run per company (a database, a scheduler, a web server), so it is offered, not required.
The point of the contract is that the pipeline is the same for every client; only the runner differs. This is what makes the Build centre repeatable.

### 4.3 SLA and contract checks
Every run records: arrived on time or late (against the contract), schema matched or drifted, rows loaded, rules passed or failed with counts, and the time the marts were ready against the SLA. These are facts in the run log and nodes on the company graph (Rule, Risk), never only a message.

### 4.4 Prove each measure
The Prover recomputes every measure from the gold marts for the periods the company has reported, and compares with the reported figure, the same test as the moment of truth but on the loaded data, not a sample. Result per measure: match, gap with a reason, or not yet. A measure is **release-ready** when it matches for every reported period in the band, or the gap has an accepted reason signed by the owner. The evidence pack per measure (figure, reported figure, difference, rule results, lineage) is the release screen.

### 4.5 Release sign-off
The sponsor signs the release for the band when every measure in it is release-ready. Signed means the marts are read-only for people and the pipelines are "live": the Watcher takes over. A measure not ready is carried to the next band with its reason; nothing is marked done that is not.

## 5. Room 3: Ops manager (the Watcher)

The Watcher is the ops agent. It runs the schedule, and after every run it checks freshness (did the file arrive when the contract says), drift (schema or volume outside the usual range), rule failures and anomalies in the measures (a value outside its own history by a stated margin). It writes everything to the run log and tells people in plain words.

Where it tells them (A-067): a channel webhook (Slack, Teams), email, or the screen, chosen in the environment check. A webhook is an **egress destination**, allowlisted per company by the company admin, and every post goes through the gateway: status, counts and measure labels, names tokenised, never a row and never a figure from a restricted measure. The daily feed is one message per company per day: what loaded, what is late, what failed, which owner is asked to act. The earlier repo's Slack checks and ops monitor are the reuse starting point.

The Ops manager screen: today's arrivals against the contract, open alerts with the owner, the run book (drawn from the contracts), the quarterly access and retention review dates from the governed state.

## 6. Human-in-the-loop, exactly

| Who | Does | When |
|---|---|---|
| Head of data | confirms five environment answers; signs the blueprint | once per band |
| IT (if named) | signs the blueprint's infra part; allowlists the webhook | once |
| Each owner | accepts or explains a gap on their measure; acts on an alert | as needed |
| Sponsor | signs the release | once per band |
| Company admin | allowlists destinations; reviews access quarterly | quarterly |

Everything else is the agents': scan, blueprint, code, tests, runs, checks, proofs, alerts.

## 7. Reuse (earlier repo, module 4 rows of `docs/reuse-inventory.md`)
Pipeline build (bronze, silver, gold; `e/pipeline_build.py`, `e/bronze_loader.py`, `e/silver_transform.py`, `e/gold_transform.py`), SQL dialect translation (`e/sql_dialect.py`), model and architecture drafting (`e/model_drafting.py`, `e/architecture_drafting.py`), test pack generation (`e/test_pack.py`), release gate and two-person sign-off (`e/release_gate.py`, `e/release_signoff.py`), screens (`s/build-package.js`, `s/build-track.js`, `s/architecture.js`, `s/reconciliation.js`), the de-bronze, de-silver, de-gold and data-architect agent definitions. The ops monitor's Slack checks from the other project are to be found and listed before BC-7 starts. New: the environment check, the three-path fit report, the blueprint JSON and its Archify rendering, the pipeline contract and the built-in runner, the Airflow generator, the Prover against the reported figure, the Watcher's webhook egress.

## 8. Packages (after the Intent centre's IC-0 to IC-3 and CG-1)

| Id | Package | Expect |
|---|---|---|
| BC-1 | Environment check: five questions prefilled from profile and constraints; environment record | Sonnet |
| BC-2 | Estate scanner: read-only metadata, three-path fit report; skipped when no warehouse | Sonnet |
| BC-3 | Blueprint: Architect agent writes blueprint.json from catalogue, trial rules, governed state, arrivals; Archify rendering; blueprint screen and sign-off | Sonnet, Opus review |
| BC-4 | Warehouse: DuckDB in the plane, bronze, silver, gold, restricted marts in a separate file, read-only copy for query tools | Sonnet, security review |
| BC-5 | Pipeline contracts and the built-in runner: contract schema, generated code, dependencies, retries, run log, SLA facts | Sonnet, Opus review |
| BC-6 | Prover and release: recompute per period, evidence pack, release-ready rule, sponsor sign-off | Sonnet |
| BC-7 | Watcher: freshness, drift, anomalies, daily feed; webhook as an allowlisted egress destination | Sonnet, security review |
| BC-8 | Airflow DAG generator from the contracts; cloud warehouse dialect and two-approver push | Sonnet |
| BC-9 | Build centre screens in the design tokens; outcomes page measures (time to first matching measure, measures release-ready, SLA met) | Haiku/Sonnet |

## 9. Decisions requested
- A-064 The warehouse is one DuckDB file per company inside the plane; a customer's cloud warehouse is a choice in the environment check, not the default.
- A-065 Restricted marts live in a separate DuckDB file readable only by the people on the list; query tools read a read-only copy, never the live file.
- A-066 Pipelines are defined as contracts (arrival, SLA, schema, rules, dependencies, owner) and compiled to code; the built-in runner is the default, an Airflow DAG is generated for customers who have Airflow.
- A-067 Webhooks (Slack, Teams) are egress destinations allowlisted per company; posts carry status, counts and labels only, through the gateway.
- A-068 A measure is release-ready only when it matches the reported figure for every period in the band, or its gap has an owner-signed reason; the sponsor signs the band.

## 10. Open questions for Nitin
1. Which webhook first: Slack or Teams? (The gateway treats them alike; the message format differs.)
2. For a customer with an existing warehouse, do we ever write into it, or only read and leave the build in the plane? My default: read only until the two-approver push.
3. The anomaly margin for the Watcher: a fixed rule (outside three months' range by more than x%) or learnt per measure? My default: fixed and stated in the contract, learnt later.
