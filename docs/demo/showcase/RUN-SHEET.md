# Signal Harbor showcase: 30-minute live demo run-sheet

For Tuesday 13 Oct 2026, 10:00, on Railway: https://signalharborv20-production.up.railway.app
Synthetic data only. The company is Evergreen Office, a fictional family office. Use no other names.

Deck: `docs/demo/showcase/index.html` (20 slides; arrow keys or click; `P` prints) or the editable `Signal-Harbor-showcase.pptx` (same 20 slides, talk track in the speaker notes).
Data shown by each screen: `docs/demo/DEMO-DATA.md`. Feature coverage: `docs/demo/COVERAGE.md`.

## Before the call (the evening before, then 09:00)

1. Open the Railway link. The sign-in page loads, then sign in once as each person in the table below. Use one browser window per person (a private window each is simplest) so you switch by clicking a window, not by signing out. First loads are slow; this warms them.
2. Passwords: never write them down, read them aloud or put them in a chat or slide. If the shared demo password is set on the service, use it. Otherwise read `/data/_control/seed_credentials.txt` yourself (`railway ssh`, then `cat`).
3. Check each screen against the table in `DEMO-DATA.md`. Minimum checks:
   - Anita: Action lists the 12,400 Entity B cash break, Waiting for my approval has Lumen's starter dashboard and plan v3.
   - Leo: Build, Operations shows Runs with TEST and PRODUCTION rows.
   - Daniel: Consume, Markets shows LIVE API tags (Frankfurter, MAS); Reports shows the published monthly dashboard.
   - Anita: Map, Data model shows the loaded tables, including `silver.entity_cash_daily`.
4. If a screen is empty or wrong, reset the demo (section at the end) before 09:30, then repeat the checks. A reset gives new sign-in details unless the shared password is set.
5. Settings, Egress: the internet switch should be on for the demo company (the seed turns it on when a provider answers). Without it, Connect an API cannot test.
6. Open `docs/demo/showcase/img/` in a second window so you can switch to a screenshot at once. Browser zoom 100 percent, window 1440 px wide or more.
7. Do not start a new project with North live. The service has a daily model spend cap and a per-person chat limit, and agent replies can be slow. Show the signed intent instead.
8. Do not edit code or press Approve on the pending plan or model change during the demo unless you mean to; reset afterwards.

## Who to sign in as

Emails are `<first>.<last>.evergreen@example.test` (for example `daniel.foo.evergreen@example.test`). Passwords: see step 2 above.

| Person | Role | Sees | Use it for |
|---|---|---|---|
| Daniel Foo | Sponsor (CIO) | Action, Build (his intent), Consume, Map; Settings 3 items | Intent, Consume |
| Mei Chen | Business owner | Action, Build (her project), Consume, Map; Settings 3 items; no Operations | Roles slide only (shows the owner's smaller menus) |
| Raj Patel | Approver | Action, Consume, Map; Settings 4 items | Optional: the approver's Action |
| Anita Rao | Head of data (also analyst) | Everything the data team sees; approves pack, plan, Map items, model changes; Settings 7 items | Design pack, Build and prove, Action, Map |
| Leo Park | Data engineer and ops | Operations, Pipelines, Connect an API; Settings 8 items | Operations, Runs, Connect an API |
| Grace Ong | Administrator | All centres; Settings 16 items | Roles slide only |
| Sofia Reyes | Risk owner (participant) | Read access, Settings 3 items | Not used |

## Run order (30 minutes)

| Time | Slide | Live step (exact clicks) | Say | Point at | If slow: use this |
|---|---|---|---|---|---|
| 0:00 to 0:03 | 1 to 3 | None; slides only | "Every figure should be able to show where it came from. Four centres, four agents; agents draft, people sign." | The four centres and four agents on slide 3 | None needed |
| 0:03 to 0:06 | 4 Intent | Daniel Foo: **Build**, open the project "Monthly performance against the office blend", **Intent**. Read the signed intent, then open the **Process map** tab. | "The sponsor signed this. It is read-only; a change is a new version." | The signature line and the process map lanes | `img/intent-ready.png` |
| 0:06 to 0:09 | 5 Design pack | Anita Rao: **Build**, the project, **Architecture**, then **Tables and SQL**, open one gold table. | "Span drafted the design. Anita approves it before anything is built. Approved means locked." | The approval state and one gold table's columns | `img/span-design-pack.png`, `img/head-of-data-approve.png` |
| 0:09 to 0:12 | 6 Build and prove | Still Anita: **Pipelines** for the project; show the last check against the September report. | "The builder ran on a copy and checked every line against the September report. All three figures matched." | The 4.17 / 2.71 / 1.46 lines with "Matches" | `img/builder-variance.png`, `img/pack-v2-approved.png`, `img/go-live.png` |
| 0:12 to 0:16 | 7 Consume | Daniel Foo: **Consume**. **Today**, then **Financial health** (try **By fund**), then **Markets**: read the FILE or LIVE API tag and date on one line of each kind. Then **Reports** (the published monthly dashboard). Press **SGD** in the currency switch at top right. | "Every outside line says where it came from and when. A missing input shows as missing." | The FILE and LIVE API tags; "Where is this from?" | `img/consume-markets.png`, `img/consume-reports.png`, `img/consume-today.png`, `img/consume-health.png` |
| 0:16 to 0:19 | 8 Action | Anita Rao: **Action**. Read the greeting and chips. Open the **Reconciliations** group: the Entity B cash break shows Tally's timing explanation. Show **Close as timing** but do not press it unless you will reset. Show **Waiting for my approval**. Click **Where is this from?** on a figure. | "Action is one page of what needs a person. Every figure shows its trail." | The one primary button on each line; the trail back to file and row | `img/action-demo.png` |
| 0:19 to 0:21 | 9 Ontology | Anita: **Map**. On **Ontology**, press **+**, **Fit**, drag. Click a node. Pick one project in **One project**. | "One graph of people, projects, data and dashboards." | The node card (owner, state, connections) | `img/map-ontology.png` |
| 0:21 to 0:23 | 10 Data model | Anita: on Map press **Data model**. Switch **Loaded** and **Whole model**. Click `silver.entity_cash_daily`, then a gold table and read **If this table changes**. | "The Map shows what each number is made of, and what a change would touch." | Bronze, silver and gold labels; the "If this table changes" list | `img/map-data-model.png` |
| 0:23 to 0:25 | 11 Operations | Leo Park: **Build**, then **Operations**. Read the tiles and Sources. Scroll to **Runs**: show a TEST row and a PRODUCTION row, click one run for its steps. Scroll to **Deliveries**. | "Is everything arriving and running? Every run has an ID." | The run ID, the TEST or PRODUCTION badge, who and trigger | `img/operations.png`, `img/operations-full.png` |
| 0:25 to 0:26 | 12 Connect an API | Leo: **Build**, **Connect an API** (also under Settings, Connectors). Show the four providers and their key status. Optional: choose Frankfurter, press **Test the connection**. Do not enter or paste any key. | "Market data comes in through the same gateway and labels as the files." | The provider list; Singapore sources (MAS) | `img/connect-api.png` |
| 0:26 to 0:27 | 13 Lineage and run IDs | Slide only. Optionally flip back to Runs or to Data model, `silver.source_batches`. | "File to batch to record to bronze to the gold table's run ID." | The chain on the slide; the amber note | None needed |
| 0:27 to 0:28 | 14 Roles | Mei Chen's window, **Settings** (3 items); Leo's (8); Grace's (16). | "Each person sees what their role needs." | The size of each Settings menu | `img/role1-settings-mei.png`, `-leo.png`, `-anita.png`, `-admin.png` |
| 0:28 to 0:29 | 15 to 17 | Slides only | Architecture: "one exit". Security: names masked, run IDs on every run. Efficiency: say which numbers are measured and which are estimates. | Slide 17 labels | None |
| 0:29 to 0:30 | 18 to 20 | Slides only | Rollout, the six decisions, questions | Slide 19 | None |

If time runs short, skip slides 15 to 17 live and offer them in the technical review.

## What to say about the numbers

- Measured in our walkthrough (11 Oct 2026, synthetic data): about 45 minutes from first words to delivery live, of which about 10 minutes was the conversation with North; four people; 26 model calls and about USD 0.01 of model cost in test mode.
- Estimated, to be validated with the client's team: the typical manual month-end (the slide says two working days). Never present the manual figure as measured.
- Sign convention: say "portfolio minus benchmark, in percentage points".

## Say plainly if asked (do not present as more than it is)

1. **Live pipelines table** on Operations reads "Not run yet" for the three file sources. The seeded runs are pipeline and reconciliation runs, not file-connector loads.
2. **Lineage edges.** The run ID is on gold tables today. The bronze load ID on the market-data loader and the run ID on silver tables are still being joined up.
3. **Market data.** Frankfurter and MAS rows are live. FRED and Finnhub rows appear only when their keys are set on the service. SGS yields are the last auction of each tenor, not a daily curve. SORA is not connected. EWS stands in for the licensed Straits Times Index.
4. **Model additions.** A proposed new silver table (here `manager_fee_schedule`) waits for the head of data; the Data model draws an addition only once approved. Span proposes gold tables itself; a new silver table needs a person to supply the model change.
5. **Email.** Nothing is sent at go-live; the Morning Note email and Slack are previews.
6. **Starter dashboard** is proposed once per project; a later pipeline change does not regenerate it.
7. **Real use** is off on the public link. The demo runs in Testing mode.
8. If anything on screen looks wrong, say "that is demo data, I will check it" and move on. Never explain a figure you cannot trace.

## Backup plan

- If a screen takes more than 20 seconds, switch to its screenshot in `img/` and say "here is what it shows" and carry on.
- If the app is down: present the 20 slides only, and use the screenshots for slides 4 to 14.
- If a question goes beyond the deck, say you will follow up in writing. Do not guess at a figure.

## Likely questions

- **Which AI models do the agents use?** The platform chooses models behind one gateway, and the office chooses the mode (testing or real use). The model list is part of the technical review under NDA, not this session.
- **Where does the data sit?** In the office's own data plane, one volume per company. Only masked text leaves, through the gateway. Raw rows never leave.
- **Who can approve?** A named person who did not make the change. The head of data approves the design, the plan and model changes; the sponsor signs the intent and approves dashboards.
- **How do I trace a number?** "Where is this from?" on the figure, then the Map's data model, and the run ID in Operations.
- **Who sees Operations and the full data model?** The data team only. Others see the gold tables of their own projects.
- **What if a number is wrong?** Every figure has "Where is this from?". A correction is a new version of the pack, shown side by side with the old one.
- **How much does it cost?** In the walkthrough, about USD 0.01 of model cost for a whole run in test mode. Production cost is a rollout item; do not quote a production figure.
- **Can we use our own cloud?** Yes, as a rollout option. Hosting is decided at the pilot stage.

## Reset the demo (from `DEMO-DATA.md`)

Use only if a screen is wrong. The reset empties the demo data and seeds it again.

```
railway ssh -- sh -c 'python tools/seed_demo_boot.py --reset --data-root "$SH_DATA_ROOT"'
railway redeploy        # the running app keeps the old warehouse file open: restart it
```

- After the redeploy, wait for the health check, then repeat the "Before the call" checks.
- A reset creates new sign-in details unless the shared demo password is set; read them yourself as in step 2. Never paste them anywhere.
- The seed turns the company's internet and connector switches on only when a provider answers, and writes no fake "live" rows if offline. Keys (`FRED_API_KEY`, `FINNHUB_API_KEY`) are service variables, never files.
- Pressing Close as timing, or approving the pending plan or model change, changes what the next screens show. Reset afterwards if you did.
