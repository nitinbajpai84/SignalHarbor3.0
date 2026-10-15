# Signal Harbor: user and testing guide for the handover team

Status: 13 October 2026. Written for the team taking over Signal Harbor.

Read this first. It explains who the people are, what each feature does, how to test it, how we tested the product, and what does not work yet.

## Before you start

- All data is synthetic. The company is **Evergreen Office**, a fictional family office. Every name, figure and file is invented.
- Sign-in details are in **the access sheet**. The administrator holds it. This guide does not contain any passwords. Never paste a password into chat, a file or a ticket.
- The demo runs in **Testing** mode. Testing uses low-cost test models. Do not switch to **Real use** for any test in this guide.
- Each person has their own sign-in. Use one private browser window per person, so you can switch between them by clicking.
- Browser zoom at 100 percent. The window should be 1440 pixels wide or more.

Hosted demo: https://signalharborv20-production.up.railway.app

Source documents this guide draws on are listed in section 6.

---

## 1. The people and their roles

Signal Harbor works with one set of seven demo people. Each one has a role. The role decides which centres they see, where they land when they sign in, and which Settings items they get.

The rules come from `ui/src/shell/roles.ts`. The server checks the same rules again. If the screen and the server disagree, the server is right and the screen is a bug.

### 1.1 The seven people

| Person | Seat in the code | What they do in the demo |
|---|---|---|
| **Mei Chen** | Owner (`owner`) | Describes the need to North. Hands the build to the data engineer. Reads Consume and Map. Works her own Action items. Cannot approve her own work |
| **Daniel Foo** | Sponsor (`sponsor`), Chief Investment Officer | Signs the intent of work. Approves dashboards and delivery channels. Reads Consume |
| **Raj Patel** | Approver (`approver`), Finance | Clears cases and confirms figures sent to him. Approves what others make, never his own work |
| **Anita Rao** | Analyst (`analyst`) and head of data (`head_of_data`) | Approves the design pack, the build plan, Map items and model changes. Sees the data team's view. The head of data seat opens no centre on its own; it is held beside the analyst seat |
| **Leo Park** | Analyst (`analyst`), data engineer | Confirms sources, uploads samples, answers design questions, runs the build, goes live. Watches Operations. Connects APIs |
| **Grace Ong** | Company administrator (`company_admin`) | Looks after access, settings and the control centre. Sees every centre. Can run the trade check in UC8 |
| **Sofia Reyes** | Participant (`participant`), risk | Reads Action, Consume and Map. Can read, ask and add notes. In the seed she cannot take, assign, approve or close cases. The UC5 test made her an owner on screen to test the risk steps |

A super administrator seat (`super_admin`) exists for the platform owner. It opens only the control centre. No demo person holds it.

### 1.2 What each person sees

"Top bar" lists the centres. "Lands on" is the first page after sign-in.

| Person | Top bar | Lands on | Settings items (from `roles.ts`) |
|---|---|---|---|
| Daniel (sponsor) | Action, Build, Consume, Map | Action | 4: What the agents remember about you, Testing or Real use, Activity trail (own), Teach the agents (Tally only) |
| Mei (owner) | Action, Build, Consume, Map | Action | 4: the three above, plus Teach the agents (Tally and Lumen) |
| Raj (approver) | Action, Build, Consume, Map | Action | 5: the three above, Teach the agents (Tally), Rules (read only) |
| Sofia (participant) | Action, Build, Consume, Map | Action | 3: the three own items |
| Leo (data engineer) | Action, Build, Consume, Map | Action | 9: the three own items, Teach the agents (Span), Identifiers and other names, Instruments and asset classes, Connectors, Jobs and events, Sources and data model (view and propose) |
| Anita (head of data) | Action, Build, Consume, Map | Action | 9: the three own items, Teach the agents (Span and Lumen), Sources and data model (decides), Rules, Identifiers and other names, Instruments and asset classes, the company's working date |
| Grace (administrator) | Action, Build, Consume, Map, plus the control centre | Action | All 18 Settings items |

Notes for the handover team:

- The top bar shows **Build** for anyone who holds the Intent seat too. Build is where a project starts.
- **Operations** is shown to the administrator and the data engineer (`canOps` in `roles.ts`). The head of data is not in that list. Check Anita's view on the hosted demo before you promise it to anyone. The run sheet uses Leo for Operations.
- The **Health** tab in Map is for the data team only.
- Older documents give different Settings counts (Mei 3, Leo 8, Anita 7, Raj 4, Grace 16). Those counts were written before "Teach the agents" was added. Trust the table above, which follows the code.
- Every role reads Consume. The figures inside it are filtered by each person's access.

### 1.3 Rules that hold for everyone

- The person who makes a thing cannot approve it.
- Approval locks the item. A change after approval is a new version. The old version stays on record.
- Agents draft. People sign and approve.
- Only the data team sees Operations and the full data view on the Map.

---

## 2. Feature tour, centre by centre

Each feature has four parts: what it does, where it is, who can use it, and how to test it in three to five steps.

Centres in bar order: **Action**, **Build**, **Consume**, **Map**. Settings sits in the account menu.

### 2.1 Intent, with North (inside Build, step 1)

#### Describe the need and sign the intent

- **What it does.** You describe a need in your own words. North asks one question at a time. It drafts the intent of work and the process map as you talk. When every section is filled, the sponsor signs. A signed intent is read only.
- **Where.** Build, then **New project** (or an open project), then **Intent**.
- **Who.** The owner (Mei) writes it. The sponsor (Daniel) signs. Changes after signing need a new version.
- **How to test.**
  1. Sign in as Mei. Open Build and start a project.
  2. Type a need in plain words. Check that North asks one question at a time.
  3. Check that the result, success test and process map fill in as you talk. Note any section left empty.
  4. Sign in as Daniel. Open the same intent, read it, and sign.
  5. Check that the signed intent is read only. Try to edit a section and confirm it is refused.

#### Hand over to the data team

- **What it does.** The owner gives the project to the data engineer. A due date is set. Each step can name who does it.
- **Where.** The project page, **Hand over** or **Send to Build**.
- **Who.** The owner or the project's owner. A past due date is refused.
- **How to test.**
  1. As Mei, open the signed project and hand it to Leo with a future due date.
  2. Try a past due date and confirm it is refused.
  3. Sign in as Leo. Check the work appears in Action under **Assigned to me**.

### 2.2 Architecture and the design pack, with Span (Build, step 2)

- **What it does.** Span reads the signed intent. It shows each source as the intent recorded it. It asks only what the intent and its scan cannot answer. Each question has a proposed answer. You upload one sample for each new source. For a PDF you mark the fields to read, once. Span drafts a versioned **design pack**. The pack holds the target model, the data catalogue, the mapping sheet, the rules and the sources.
- **Where.** Build, the project, **Architecture**. Span's talk box is also here.
- **Who.** The data engineer (Leo) works it. The head of data (Anita) approves the pack. Mei cannot confirm extracted PDF fields (403, data team only).
- **How to test.**
  1. As Leo, open the project's Architecture. Confirm the sources. Check none was re-typed.
  2. Answer the questions. Accept at least one proposed answer.
  3. Upload one CSV sample and one PDF. Mark the PDF fields.
  4. Draft the pack. Settle every open row with a note. Send to the head of data.
  5. As Anita, approve the pack. Then check the build plan is approved too. Note any step that still says "not approved yet".

Known: the pack can gain open rows that need decisions from later steps (UC6 finding M8). Span's gold SQL can fail on the product's own guard. See section 8.

### 2.3 Pipelines and the benchmark check (Build, step 3)

- **What it does.** The builder connects each source the approved pack names. It runs on a copy first (a **TEST** run). It asks for last month's report and compares each figure line by line, showing a variance for each. If something does not match, the case goes back to the architect as a new pack version. When the check is clean, the person presses **Go live**. The schedule comes from the pack. Go live creates a **PRODUCTION** run.
- **Where.** Build, the project, **Pipelines**.
- **Who.** Leo runs and goes live. Anita approves the plan and any new pack version.
- **How to test.**
  1. As Leo, open Pipelines. Start a run on a copy. Confirm it shows as TEST.
  2. Upload last month's report for the check. Read each variance line.
  3. Introduce a mismatch on purpose (for example, a wrong figure in a test file). Confirm the case goes back to the architect.
  4. Restore the file. Run again. Confirm the variance lines match.
  5. Press **Go live**. Confirm a PRODUCTION run appears in Operations, Runs.

For the September walkthrough the check showed 4.17 percent for the portfolio, 2.71 percent for the benchmark and 1.46 points of difference. The builder's run gave 4.1667, 2.7072 and 1.4595. Every compared line matched.

### 2.4 Dashboard studio, with Lumen (Build, step 4)

Covered in full in section 3. Quick test:

- As Leo or Anita, open Build, the project, **Dashboard studio**. Lumen's starter dashboard appears once the pipeline is live.
- Press **Accept as it is**, then **Send for approval**. Sign in as Daniel and approve.

### 2.5 Connect an API (Build)

- **What it does.** Adds a public data service on a schedule. Choose a service and series, test it, then save. A daily pull runs at 05:30 after you save.
- **Where.** Build, **Connect an API**. Also under Settings, Connectors.
- **Who.** The data engineer (Leo) and the administrator. Keys are stored by the administrator.
- **How to test.**
  1. Check Settings, Egress. The company internet switch must be on.
  2. Open Connect an API. Choose Frankfurter (no key) and a series, for example USD/SGD.
  3. Press **Test the connection**. You should see real rows and the time taken.
  4. Save. Open Connectors and check the new connection appears. Fetch it once.
  5. Turn the internet switch off and test again. Confirm the test is refused with a clear message. Turn it back on.

Each service has one fixed address. A pull can reach only that address and only public series. A key is read by its environment variable name and never shown on screen.

| Service | What it gives | Key |
|---|---|---|
| **Frankfurter** (ECB reference rates) | USD/SGD, EUR/USD, EUR/SGD, GBP/USD | None |
| **FRED** (US Federal Reserve) | US 10-year (DGS10) and 2-year (DGS2) Treasury yields, SGD per USD (DEXSIUS), Singapore CPI | Free key, set on the server as `FRED_API_KEY` |
| **Finnhub** | Quotes for EWS, ACWI and AGG, and market news | Free key, set on the server as `FINNHUB_API_KEY` |
| **MAS** (Monetary Authority of Singapore) | Singapore Government Securities auction yields, 2 to 30 years | None |

### 2.6 Operations (Build, data team)

Operations asks: is everything arriving and running? It has four tiles and four sections.

- **Sources.** Each source, its owner, when it last arrived, whether it is late, files turned away, old values and open breaks.
- **Live pipelines.** Each pipeline that has gone live, its last production run, its checks and its next scheduled run. Known: a fresh test environment says "No pipeline is live yet". The seeded demo shows two of two healthy.
- **Runs.** See section 2.7.
- **Deliveries.** The Morning Note preview and the Slack preview, and what is waiting to go out. Nothing is sent by the product at go-live.

Anything wrong in Operations also lands in Action for the person who owns it.

### 2.7 Operations, Runs and run IDs

Every run gets a run ID, for example `run-20261012-131500-ab12`.

- **What it covers.** Pipeline runs, file loads, connector pulls, reconciliations and limit checks.
- **What it records.** Who started it, what triggered it (by hand, on schedule, when a file arrived, or by a connector), and its steps. A badge says **TEST** (on a copy) or **PRODUCTION** (live).
- **Where.** Build, Operations, **Runs**.
- **Who.** The data team. Mei cannot see Operations.
- **How to test.**
  1. As Leo, open Operations, Runs. Find one TEST row and one PRODUCTION row.
  2. Click a run. Check its steps are listed.
  3. Copy its run ID. Find the same ID on a gold table in Map, Data model.
  4. Check the badge matches the mode. Note any run marked PRODUCTION while the company is in Testing mode. UC6 found this (finding L10).

Known gaps: a limits run cannot be marked as a test run (UC5 gap C9). Recon runs record "system" as the actor, not the person who pressed Run now (UC8 finding m3).

### 2.8 Consume: Today

- **What it does.** The Morning Note: one sentence, four key numbers (net asset value today, yesterday's profit and loss, this month's profit and loss, each against the benchmark), what moved and the markets in one line. Comments and Ask Lumen sit at the foot.
- **Where.** Consume, **Today**.
- **Who.** Everyone. Figures are filtered by each person's access.
- **How to test.**
  1. Sign in as Daniel. Open Consume, Today.
  2. Check the four numbers and the one-sentence summary.
  3. Use the currency switch (top right) to change USD to SGD. Check the figures change.
  4. Post a comment on the note. Check it appears.
  5. Ask Lumen one question about a figure. Check the answer names its source.

### 2.9 Consume: Financial health

- **What it does.** Daily profit and loss, net asset value, and fund performance in one table. Switch between **By portfolio**, **By entity** and **By fund**. Each line shows how far you can trust the value.
- **Where.** Consume, **Financial health**.
- **How to test.**
  1. Open the page. Switch between the three views. Check the totals agree across views.
  2. Find the trust column on a line marked as missing or estimated. Check the label is plain.
  3. Switch the currency to SGD. Check the table still shows the same line items.

### 2.10 Consume: Markets

- **What it does.** The market table, the office's own figures against it, and what to watch. Every outside line shows its source, its date and a tag: **FILE** or **LIVE API**.
- **Where.** Consume, **Markets**.
- **How to test.**
  1. Open Markets. Find one FILE line and one LIVE API line.
  2. Check each line shows a source and a date.
  3. For a LIVE API line, go to Build, Connect an API, and confirm the series exists.
  4. Note any "not connected" line. SORA is not connected yet (section 8).

### 2.11 Consume: Reports

- **What it does.** The report library: reports shared with you and dashboards published from the studio.
- **Where.** Consume, **Reports**.
- **Who.** Everyone sees what is shared with them.
- **How to test.**
  1. Sign in as Raj. Open Reports. Find the signed September report and the published monthly dashboard.
  2. Open the dashboard. Check each tile shows a source.
  3. Sign in as Sofia. Check she sees only what is shared with her.

### 2.12 Consume: What if

- **What it does.** Attribution: what would have changed the result.
- **Where.** Consume, **What if**.
- **How to test.** Open the page. Check the page loads, that the figures add up to the total change, and that switching the currency keeps the total.

### 2.13 Action, with Tally

Action is the one page of things that need you today. The greeting says how many items wait. Each group says "Nothing to clear" when empty.

| Group | What it holds | What you can do |
|---|---|---|
| **Cases** | Open issues | Take the case, or open it |
| **Reconciliations** | Checks that do not match, including cash, limits and trades | Close as timing (only when the cause is timing and the system allows it), or open the case |
| **Statements to chase** | Late fund statements | Draft a follow-up. You copy it and send it yourself. Nothing is sent by the product |
| **Figures to confirm** | Figures read from files | Confirm, or correct in the review queue |
| **Waiting for my approval** | Designs, plans, dashboards, deliveries, Map items and model changes | Review and approve |
| **Assigned to me**, **Waiting on others** | Your items, and items you wait on | Open or mark done |
| **Done today** | What the team closed today | Read only |

The side panel has **Ask Tally**, **My tickets** and **Since yesterday**. Action shows only the groups your role can use.

#### Ask Tally and cases

- **What it does.** Tally helps with a case and answers questions about it. It does not decide. It does not change a figure. Official figures change only through a recorded source and an approver.
- **Where.** Action, open a case, the **Ask Tally** box.
- **How to test.**
  1. Sign in as Anita. Open the Entity B cash break under Reconciliations.
  2. Ask: "Is this timing?" Check Tally's answer names the cause and the records behind it.
  3. Ask it to change a figure. Check it refuses.
  4. Click **Where is this from?** on a figure. Check the trail goes back to the file and row.

#### Reconciliations and close as timing

- **What it does.** Shows each break: cash, limits, trades. You can close a break as timing only when its cause really is timing and the system allows you.
- **How to test.**
  1. As Anita, open a timing break and try **Close as timing**. Record whether it is allowed.
  2. As Mei, try the same break. Record whether she is refused. The result shows who may close as timing.
  3. Open a non-timing break instead. Check the option is not offered.

#### Statements to chase

- **How to test.** Open the group. Press **Draft a follow-up**. Copy the draft. Check nothing was sent from the product.

#### Figures to confirm

- **How to test.** As Leo, press **Confirm** on one figure. As Mei, try to confirm an extracted PDF field and expect a refusal (data team only). Correct a figure and check it opens the review queue.

#### Waiting for my approval

- **How to test.** As Daniel, open an item waiting for approval (for example a dashboard). Approve it. Confirm the maker cannot approve their own item. Send one back with a reason and check the maker sees it.

#### Capital calls

- **What it does.** A confirmed capital call due within the signed window (default 30 days) opens a Finance case, **Fund the capital call**. A noticed call that is not confirmed does not.
- **Known problem.** A call that was already paid can still raise a case (UC6 finding M7). See section 8.
- **How to test.** Load a confirmed call due within 30 days. Check the case appears in Raj's Action. Then mark it paid, reload and check the case is closed. If the case stays open, record it as a finding.

#### Managers inbox

- **What it does.** Lists the fund managers, what each sent, and what is late. Each late statement has a **Draft a follow-up** action.
- **Where.** Action, **Managers**.
- **How to test.** Open Managers. Check each late statement shows the number of business days late. Draft one follow-up. Check nothing is sent.

### 2.14 Map

Map is one page with four views, chosen with the switch at the top.

#### Ontology

- **What it does.** The whole company as one graph: people, projects, sources, tables, dashboards and reports, cases and decisions. Click a node to see its owner, state and links.
- **Zoom and move.** Plus and minus buttons, or hold Ctrl and use the wheel (or pinch) to zoom at the pointer. **Fit** resets the view. Drag to move around.
- **Who.** Everyone with Map. Full data sits with the data team.
- **How to test.**
  1. Sign in as Anita. Open Map, Ontology.
  2. Press **+** three times, then **Fit**. Check the view resets.
  3. Drag the graph. Check it moves.
  4. Click a project node. Check the owner and state show.
  5. Use the **One project** filter. Check only that project's nodes remain.

#### Process map

- **What it does.** The steps of each project, one project at a time.
- **How to test.** Open Process map. Pick a project. Check each step has an owner.

#### Data model

- **What it does.** The data tables in three layers: **bronze** (as received), **silver** (cleaned and joined) and **gold** (what reports read). Each table shows its row count. Pick a table to see its columns, its meaning, its owner and what it reads.
- **If this table changes.** Shows the gold tables, dashboards, reports and projects that depend on the table.
- **Loaded or Whole model.** **Loaded** shows tables that hold rows today. **Whole model** shows every table, with empty ones dimmed.
- **Added for this office.** Tables added after approval sit in their own group with a dashed outline. A pending proposal is not drawn until someone approves it.
- **Who.** The data team sees every layer. Others see the gold tables of the projects they may see.
- **How to test.**
  1. As Anita, open Data model. Switch between Loaded and Whole model. Check the counts change.
  2. Click `silver.entity_cash_daily` (loaded). Read its columns.
  3. Click a gold table. Read **If this table changes**.
  4. Look for the pending proposal `manager_fee_schedule`. Check it is shown as pending, not as a loaded table.

#### Business glossary

- **What it does.** The signed definitions of each figure.
- **How to test.** Open the glossary. Find a figure. Check its definition has a signed date and a signer.

#### Review queue (head of data)

- **What it does.** Map items waiting for the head of data to verify.
- **How to test.** As Anita, open the review queue. Verify one item. Sign in as Leo and check he cannot verify it himself.

### 2.15 Settings

- **What it does.** Each person's own items, plus extra items by role. See section 1.2 for the list each person gets.
- **Where.** The account menu, **Settings**.
- **The common items.**
  - **What the agents remember about you.** Your own memory. See section 4 for taught knowledge.
  - **Testing or Real use.** The model switch. See section 5.
  - **Activity trail.** Signed intents, measures, rules, plans and the newest runs. The data team sees every row. Everyone else sees their own.
- **The data team items.** Rules (read only for the approver), Identifiers and other names, Instruments and asset classes, Sources and data model, Connectors, Jobs and events, the company's working date.
- **The administrator items.** People and access, Delivery channels, Intent admin, Templates and skills, Outside assistants, Agent runs and cost, Egress (the internet switch), and the rest.
- **How to test.**
  1. Sign in as each of the seven people. Count the Settings items. Compare with section 1.2.
  2. As Grace, open Egress. Check the internet switch shows its state.
  3. As Grace, open Delivery channels. As Leo, check the channel item is not offered (the server refuses it to everyone else).
  4. As Mei, open the Activity trail. Check it shows only her own rows.

---

## 3. The dashboard studio

The studio is where a dashboard is built and changed. Lumen proposes tiles. People decide. The route is Build, the project, **Dashboard studio**.

The studio is for data-team members to start, and for the owner and sponsor to read and approve.

### 3.1 Talk to change the board

- **What it does.** Type what you want in plain words. Lumen places the tile on the board at once. If a tile is selected, the talk is about that tile only.
- **Where.** **Talk to Lumen**, under the grid.
- **Example asks.** "Add cash by entity as bars." "Make it dots." "Show net worth USD by entity per month as a line chart."
- **How to test.**
  1. As Leo, open the studio. Type "Add cash by entity as bars". Check a new tile appears in an empty slot.
  2. Select one tile. Type "Make it a line chart". Check only that tile changes.
  3. Type a request Lumen cannot meet, for example a figure that is not in the data. Check it says so and does not invent a number.
  4. Check every change adds a step in History (section 3.2).

### 3.2 Undo and History

- **What it does.** Every change is a numbered step. The studio keeps the last 50 steps.
- **Undo.** Steps back one change.
- **History.** Opens a drawer with every step: who, when, what was said, and a summary. Each step has **Go back here**, **Compare with now** and a view of the differences (added, removed, changed tiles).
- **Draft actions.** **Discard draft** (only before a draft has ever been published). **Withdraw from approval** pulls a sent draft back to keep editing. Archived drafts can be shown again with **Show archived drafts**.
- **How to test.**
  1. Make three changes. Press **Undo** twice. Check the board goes back two steps.
  2. Open **History**. Pick the first step and press **Go back here**. Check the board matches that step.
  3. Pick a step and press **Compare with now**. Check the listed additions, removals and changes match what you did.
  4. Send a draft for approval, then press **Withdraw from approval**. Check it is a draft again.

### 3.3 The inspector: "This chart"

- **What it does.** Change the selected chart from one panel.
- **Where.** The **Inspector** panel, the tab named **This chart**. Click a chart on the canvas to select it.
- **Settings you can change.**
  - **Chart type.** Figure, Lines, Table, Status list, Bullet (against a target), Waterfall (what moved it), Small charts (one per group), Calendar heat map, Treemap (shares), Strip of key figures.
  - **Shown as.** Down the side, across, or keep as it is.
  - **Split by** a column, or no split.
  - **Only, column** and **Only these values**: keep only the rows you choose.
  - **Title.**
  - **Duplicate** and **Remove**.
- **How to test.**
  1. Select a line chart. Change **Shown as** to a bar chart (or the matching option). Check it redraws.
  2. Set **Split by** to entity. Check the chart splits.
  3. Set **Only these values** to two entities. Check the chart shows only those two.
  4. Press **Duplicate**. Check a copy appears. Press **Remove** on the copy.
  5. Check each change is a step in History.

### 3.4 Drag to move and corner resize

- **What it does.** Drag a tile to move it. Drag its bottom-right corner to make it wider or taller. The chart fills the box.
- **Snap.** Width snaps to a quarter of the grid (12 columns). Height snaps to whole rows, from 1 to 4.
- **Without a mouse.** Select a tile, then use the **Move up**, **Move down**, **Move left**, **Move right**, **Taller** and **Shorter** buttons, or the **More** menu. The keys do the same.
- **How to test.**
  1. Drag one tile to an empty slot. Check it lands on the slot.
  2. Drag onto an occupied slot. Check it is refused with "That place is taken or off the grid".
  3. Drag a corner to make a tile wider. Check it snaps.
  4. Use the **Taller** button. Check the height steps by one row.
  5. Check each move is a step in History.

### 3.5 Three options, backed by industry practice

- **What it does.** For any tile, Lumen offers three ways to show the same data. One is marked **Lumen's pick**. Each option has a short "why" line.
- **How the pick is made.** The options come from the table's columns. The pick follows the words the person used. For example "per day" or "monthly" points to a trend. "Against" or "target" points to a bullet chart. Lumen also looks for the matching passage in what the agents were taught (section 4). The "why" line says which kind of practice it follows.
- **How to apply.** Press **Use this** on an option. If you choose another way, Lumen does it your way.
- **How to test.**
  1. Select a tile. Press **Show me 3 options**.
  2. Check three options appear, with one marked Lumen's pick.
  3. Read each "why" line. Check it matches the option.
  4. Press **Use this** on a non-pick option. Check the tile changes.
  5. Ask in words: "per day, as a trend". Check the pick becomes a trend chart.

### 3.6 Chart checks before publishing

- **What it does.** Lumen checks the dashboard before anyone reads it. Each check is rules only. No model is called.
- **The five checks.**
  - **Counted twice.** The same money added up twice, for example two sources stacked.
  - **Trend flattened.** A line that looks flat only because the scale starts at zero. The fix moves the scale to the data.
  - **Space.** Wasted space or a tile too small for its data.
  - **House style.** Chart choices outside the house style.
  - **Too many.** More tiles on one page than the limit in the code (nine).
- **Each check offers a one-click fix.** A fix is applied once. A fixed check disappears.
- **Where.** The **Checks** panel.
- **How to test.**
  1. Make a stacked chart that adds up one money figure from two sources. Open **Checks**. Check "Counted twice" appears.
  2. Press the fix. Check the stack is split and the check clears.
  3. Make a line chart with a scale from zero and a small range. Check "Trend flattened" appears. Apply the fix.
  4. Add a tenth tile. Check "Too many" appears.
  5. Send for approval and check the checks are shown on the approval panel under **What Lumen checked**.

### 3.7 Sketch to dashboard

- **What it does.** You draw a dashboard on paper, photograph it, and upload the picture. Lumen reads the boxes and labels on the machine. The picture is never sent out. Lumen then says which boxes it can build.
- **Each box gets one status.**
  - **Possible today.** A gold table and a measure were found.
  - **Needs a definition.** Data was found but the match is unclear. Lumen asks one question.
  - **Not possible yet.** No data is held for the box. Lumen says what source is needed.
- **Build and request.** Build the boxes that are possible. Send the missing items to the data team as a Build request.
- **Limits.** Picture up to 5 MB. Up to 30 boxes. If the local reader is missing, type one label per line instead.
- **How to test.**
  1. Draw four boxes on paper: one for cash by entity, one for a figure with no data (for example "sector heat map of private equity deals"), one ambiguous label, and one title.
  2. Upload the photo. Press **Read my sketch**. Check the boxes appear with a status.
  3. Check the box with no data says "Not possible yet" and names the source needed.
  4. Build the possible boxes. Check the new tiles appear on the board.
  5. Check the network log shows the picture was not sent to any outside address.

### 3.8 The new chart types

| Name on screen | Chart | Use it for |
|---|---|---|
| Against a target (bullet) | A figure against its target or limit | Limits, budgets, benchmarks |
| What moved it (waterfall) | Bridge from a start total to an end total | What changed a total |
| One small chart each (small multiples) | One small chart per entity, on the same scale | Comparing entities or funds fairly |
| Calendar | Heat map of what falls due on each day | Calls, payments, deadlines |
| Share map (treemap) | Boxes sized by share of the whole | Holdings and shares |
| Headline strip (KPI strip) | A row of key figures | The headline numbers |

- **How to test.** Make one of each on synthetic data. Check each has a title, a legend or label for each value, and a source line. Check the figures match a table in Map, Data model.

---

## 4. Teach the agents

People can add files and notes for one agent at a time. The agent then uses the taught passages when it answers.

- **Where.** Settings, **Teach the agents**. Each person sees only the agents they may teach.
- **Who can teach which agent.** The server enforces this. The menu follows it.

| Agent | Who may teach |
|---|---|
| **Span** | Head of data, data engineer (analyst), administrator |
| **North** | Administrator |
| **Tally** | Owner, sponsor, approver, administrator |
| **Lumen** | Owner, head of data, administrator |

### 4.1 Upload a book or a note

- **What you can add.** PDF, Word, Excel or text files. Or a short note.
- **Size.** A file can be up to **150 MB**. A whole book as a PDF is mostly page images, so only its text is indexed.
- **Refused.** Pictures cannot be taught. A file with no readable text is refused at once.
- **Note.** Notes are up to 6,000 characters.
- **Several files.** Pick several files to add many books at once.
- **How to test.**
  1. Sign in as Anita. Open Settings, Teach the agents. Choose Span.
  2. Add a short note with a title. Check it appears in the list with your name and the date.
  3. Upload a 20 MB text-based PDF. Check it is accepted.
  4. Try a picture file. Check it is refused with a plain message.
  5. As Raj, check Teach the agents lists Tally only.

### 4.2 Rule notes (house rules)

- **What they are.** A note marked **always** is a house rule. It rides with every question the agent answers, whatever the question. The page calls them **House rules (every answer)**.
- **Size.** Up to 4,000 characters in all for house rules.
- **How to test.** Mark one note as always. Ask Tally any question on a case. Check the answer follows the rule. Switch the note off and check the rule no longer applies.

### 4.3 How a taught passage is used

- **What happens.** The question is searched against the agent's active items only. At most four passages, about 1,500 characters, are added. Person-like names are masked.
- **The "Used:" line.** An answer that used taught text shows a line under it. Example: "Used: Month end checks, passage 2". A reply worded only by the fixed rules shows no line.
- **How to test.**
  1. Teach Tally a note: "Rebalancing timing: wait five business days after a fund notice." (Test text only.)
  2. As Mei, open a case. Ask Tally: "When should we rebalance?"
  3. Check the answer shows "Used:" with the note's title.
  4. Ask an unrelated question. Check there is no "Used:" line.
  5. Switch the note off. Ask again. Check the "Used:" line is gone.

### 4.4 Always-on playbooks

- **What they are.** Each agent has a folder of plain files: a playbook, questions, traps and examples. They load into the agent's standing instructions for every turn. Together they are trimmed to 6,000 characters.
- **Where.** The repository's `skills` folder, one folder per agent. A company can add its own files in its own copy, which replace the repository's files of the same name.
- **How to test.** Open the agent's playbook. Change one line in a test copy. Check the agent's next answer follows it. Put the original back.

### 4.5 Activity trail

Every add, switch-off, switch-on and replacement is a row in the activity trail, shown as "Taught Tally: Rebalancing timing (added)". The data team sees everyone's rows. Others see their own.

---

## 5. Voice, Testing vs Real use, and market data

### 5.1 Voice

- **What it does.** In the North private room, a microphone lets you speak to North. A spoken-replies switch reads answers aloud. A play button replays an answer.
- **Where.** Build, Intent, the private room.
- **Failure.** If speech cannot be used, you are told in one plain line and can carry on by typing.
- **How to test.**
  1. Open the private room. Press the microphone. Say one sentence. Check it is typed into the box.
  2. Turn on spoken replies. Ask a question. Check the answer is read aloud.
  3. Deny microphone access in the browser. Check the one-line message and that typing still works.

### 5.2 Testing vs Real use

- **What it does.** One switch in the top bar sets the model for the whole company. **Testing** uses the free model tier, for trying things. **Real use** uses the company's chosen models.
- **Where.** The top bar, **Models: Testing or Real use**.
- **Who can switch.** The administrator or the sponsor (Grace or Daniel in the demo). Others see the switch, but the server refuses with "Only the company administrator or the sponsor can do this" (checked on the hosted demo, 13 October).
- **How to test.**
  1. Note the current mode in the top bar.
  2. Switch to Real use. Check the line under the agent changes.
  3. Switch back to Testing. Check it changes back.
  4. Check every role sees the current mode, even if only some can switch it.

Do not run any check in this guide in Real use.

### 5.3 Market data connectors

Market data comes in through the same gateway and labels as the files. Four providers are fixed.

- **Internet switch.** All four providers need the company internet switch on (Settings, Egress).
- **Daily pull.** A saved connection pulls at 05:30 each day. You can also fetch it now from Connectors.
- **Labels.** Every outside line in Consume, Markets shows its source, its date and a tag: FILE or LIVE API.
- **Limits.**
  - MAS gives the yield at the last auction of each term, not a daily curve.
  - EWS stands in for the Straits Times Index, which is licensed.
  - The daily Singapore overnight rate (SORA) is not connected yet.
  - FRED and Finnhub rows appear only when their keys are set on the server.

---

## 6. How we tested

### 6.1 The method

- We take a real family-office question and run it end to end.
- All data is synthetic. Evergreen Office is invented.
- We run month by month: a build month, then the months after.
- Each step is done as the person who would do it. The owner, sponsor, data engineer, head of data and approver all act in their own sign-in.
- Every figure is checked against an answer key written before the run.
- Every run has a run ID, so a figure can be traced to its files.
- What breaks is written down, fixed where we could, and run again.

### 6.2 The ten use cases

| Code | Use case | The question it answers |
|---|---|---|
| UC1 | P&L and NAV explanation | Why did NAV move this month? |
| UC2 | Reconciliation and break desk | Where do two records of the same money disagree? |
| UC3 | Manager information inbox | What did our managers send, and what is late? |
| UC4 | Certified reporting and benchmark | Is the signed monthly report right against the benchmark? |
| UC5 | Allocation and limit monitoring | Are we inside our limits? |
| UC6 | Private-asset liquidity and commitments | Can we meet the capital calls? |
| UC7 | Manager diligence research | What do we know about this manager, in one place? |
| UC8 | Trade and valuation control | Do our trades agree with the administrator? |
| UC9 | Process map and SOP builder | How is the monthly work done, step by step? |
| UC10 | Data pipeline and insight builder | How does a question become a live dashboard? |

We ran **UC5, UC6 and UC8** month by month, on the same path: intent, design, builder on a copy, go live, dashboard, action. They load new files every month, so the whole data path is tested. Each one ends in something a person uses.

Read the full reports before you rely on any result:

- UC5: `docs/test/uc-live/UC5-REPORT.md` (plan `UC5-PLAN.md`, runbook `UC5-RUNBOOK.md`)
- UC6: `docs/test/uc-live/UC6-REPORT.md` (plan `UC6-PLAN.md`, runbook `UC6-RUNBOOK.md`)
- UC8: `docs/test/uc-live/UC8-REPORT.md` (plan `UC8-PLAN.md`, runbook `UC8-RUNBOOK.md`)

### 6.3 UC5: are we inside our limits? (monthly limit check)

**Result, honest.** The limit arithmetic matches the answer key for July, August and September. October is not right yet.

- **July to September.** Harborview, listed equity, the Cedarpoint pair, hedge funds and the Pacific Rim question all matched the key within tolerance. Harborview was 5.73 percent of a 6 percent cap in July (inside), 5.71 percent in August (inside), and 5.75 percent of a 5 percent cap in September (a real breach, over by 308,000).
- **The cap question.** The seeded register said 5 percent. The signed workbook said 6 percent from 1 January. The run used the signed 6 percent for January to August. The decision on which cap is in force belongs to the CIO. Check the figure in force before you rely on a July result.
- **Found and fixed in the test.** A file loaded late never counted for the day it arrived. A standing breach opened a new case each month. The administrator's totals block under the data was ignored. Limit changes had to be typed in by hand. Each was changed and tested.
- **Still open.**
  - **G-1.** A limits view on the dashboard in Consume. The dashboard tiles showed one wrong number (290,850,433 under every limit) and were fixed. No limit figure is on the dashboard yet.
  - **G-2.** October's new valuations, which come in the administrator file, never reach the check. October runs, but every limit figure is still September's.
- **Verdict for the risk owner.** Usable each month on the Reconciliations screen, with the files' receipt time. Not yet usable in Consume, and not yet for October.

### 6.4 UC6: can we meet the capital calls? (liquidity and commitments)

**Result.** July and August completed, with four workarounds.

- **Cash by entity matched the key to the cent** in both months. For example, EG-HOLD 2,305,906.48 in July, EG-TRUST 1,252,492.34, EG-B 905,000.00, and the three-entity total of 4,463,398.82. August: 4,141,334.77 for the total.
- **Calls due in 30 and 60 days, shortfall.** None, as the key expects, in both months.
- **Uncalled commitment.** July matched 13,450,000. In August, confirming one late notice moved Entity B's uncalled commitment from 8,900,000 to 13,100,000, so the total showed 17,650,000 against a key of 13,450,000. This was a wrong number, found in the test.
- **Found in the test:**
  - Span's first gold SQL was refused by the product's own guard, and was wrong where it did parse. The guard reads the word "call" as a forbidden word. A person rewrote the select.
  - North listed some figures as sources, so the builder asked for samples that never arrive for those phantom sources.
  - The called-to-date figure switched from the opening balance to confirmed notices only, dropping the 4.5 million already called.
  - Action raised a "Fund the capital call" case for a call paid on 23 July.
- **Fixes made after the test.** These four were fixed after the test: Span's gold SQL, the uncalled amount, extra sources, and called-to-date. The report does not re-run the test on the fixes. A re-run is the first regression step in section 7.
- **Still open.** A paid capital call can still raise an Action case. Treat any "Fund the capital call" case as unconfirmed until someone checks the payment.
- **Verdict.** The plumbing from intake to a live run works. The product is not yet one a family office could run unattended. The gold design must run without a hand rewrite, and a confirmed notice must not move the uncalled figure by millions.

### 6.5 UC8: do our trades agree with the administrator? (trade control)

**Result.** Blocked at loading in the first month, July. Not run past that point. A re-run is pending.

- Intent, signature and design approval all worked, with three workarounds.
- July's trades did not reach the silver `transactions` table. No product path loads the trade files into that table. The trade check therefore compared zero trades and reported "Nothing was reported on either side". The answer key expects four compared and four matched.
- The design pack had no gold or silver tables. Span drafted no table for FX confirmations.
- The trade check itself works. It holds the signed 5,000 USD allowance.
- August to October were not attempted. Without a load path they would only repeat the empty check.
- **Needed before a re-run.** A trade loader into silver `transactions`, from the trading export and the administrator trade file. Then rerun the runbook from the load step.
- **Money spent.** About USD 0.008 for 22 model calls in test mode.

### 6.6 Automated test suites

The team's figure is about **4,300 backend tests** and about **1,800 UI tests**. Counts depend on how parametrised cases are counted.

Counts in the source on 13 October 2026:

- Backend: 3,682 test functions in 357 files under `tests/`. Use `pytest --collect-only -q` for the exact collected count.
- UI: 1,757 test cases in 219 files under `ui/src/` (`it` and `test` calls).

Last complete backend run (13 October, with the dashboard studio and UC6 fixes): **4,310 passed, 74 skipped, 1 failed**. The failure was the warehouse lock test, which clashes with a running local server and passes on its own. Full UI run the same day: 1,814 passed, 1 flaky voice test that passes on its own. Later fixes that day (chart readability, the number guard, Tally speed) were checked with their own test files, not a new full run. Run the whole suite before you release anything.

How to run:

- Backend: `python -m pytest -q` from the repository root, with a basetemp outside the repo (for example `--basetemp=D:/Temp/pyt-run`) and `-p no:cacheprovider`.
- UI: `cd ui`, then `npx vitest run` and `npx tsc --noEmit`.
- Do not use the repository `data/` folder for tests. Do not use ports 8400, 8504 or 8200 for tests.

### 6.7 Live checks on the hosted demo

The hosted demo is seeded at boot with the Evergreen Office data. Before a call or a release:

1. Open the hosted link. Sign in once as each person, using the access sheet.
2. Check each screen against the table below.
3. If a screen is wrong, reset the demo (section 6.8) and check again.

| Sign in as | Check |
|---|---|
| Anita | Action lists the 12,400 Entity B cash break with Tally's timing explanation. Waiting for my approval holds the starter dashboard and the pending model change. Map, Data model shows the loaded tables, including `silver.entity_cash_daily` |
| Leo | Build, Operations shows Runs with TEST and PRODUCTION rows. Connect an API shows four providers and their key status |
| Daniel | Consume, Markets shows LIVE API tags (Frankfurter and MAS). Consume, Reports shows the published monthly dashboard |
| Mei | Build shows her project. Action may show statements to chase (Cedarpoint Opportunities II, June statement missing). Known conflict: `roles.ts` does not list Reconciliations or Statements for the owner, so check which is right before you promise it (section 8.4, item 38) |
| Grace | Settings shows 18 items. Egress shows the internet switch on |

The demo shows **Not run yet** on Operations for three file sources. Seeded runs are pipeline and reconciliation runs, not file-connector loads. FRED and Finnhub rows appear only when their keys are set on the server.

Measured in the walkthrough (11 October 2026, synthetic data): about 45 minutes from first words to delivery, of which about 10 minutes was the talk with North. The manual month-end figure in the deck is an estimate, not a measurement.

### 6.8 Reset the demo

Use only when a screen is wrong. A reset empties the demo data and seeds it again. A reset gives new sign-in details unless the shared password is set. Read the new details from the access sheet, never from chat.

```
railway ssh -- sh -c 'python tools/seed_demo_boot.py --reset --data-root "$SH_DATA_ROOT"'
railway redeploy
```

Then wait for the health check and repeat section 6.7. The running app keeps the old file open until the redeploy.

---

## 7. Regression checklist

Run these by hand after each release. Use the hosted demo or a test copy. Tick each one. Write down any that fail, with the run ID or the screen name.

| # | Check | Where | Pass when |
|---|---|---|---|
| 1 | Each of the seven people signs in | Sign-in page | Each lands on Action |
| 2 | Action counts match the greeting | Action | Chip counts match the group sizes |
| 3 | Mei does not see Reconciliations | Action, as Mei | The group is not offered |
| 4 | Entity B cash break shows Tally's explanation | Action, as Anita | Explanation names the wire |
| 5 | "Where is this from?" opens the trail | Any figure | Trail reaches the file and row |
| 6 | North asks one question at a time | Build, Intent | Each reply has one question |
| 7 | Sponsor signs; signed intent is read only | Intent, as Daniel | Edits refused after signing |
| 8 | Maker cannot approve own pack | Architecture, as Leo | Approval refused |
| 9 | Span questions have proposed answers | Architecture | Each question has a proposal |
| 10 | Test run shows TEST; go live shows PRODUCTION | Pipelines, Operations | Badges match |
| 11 | Variance lines show for the benchmark | Pipelines | Each compared line has a variance |
| 12 | Operations Runs rows have run IDs | Operations, Runs | Every row has an ID and a badge |
| 13 | Deliveries shows a preview, nothing sent | Operations, Deliveries | Outbox empty or marked preview |
| 14 | Connect an API test returns rows and timing | Connect an API | Real rows and a time |
| 15 | Internet switch off refuses a test | Settings, Egress | Clear refusal |
| 16 | Consume Today shows four numbers | Consume, Today | Four numbers and the note |
| 17 | USD/SGD switch stays across pages | Consume | Setting kept when moving pages |
| 18 | Markets lines show FILE or LIVE API and a date | Consume, Markets | Each line tagged and dated |
| 19 | Map ontology zooms, fits and moves | Map, Ontology | +, Fit and drag all work |
| 20 | Data model: Loaded and Whole model differ | Map, Data model | Counts change between views |
| 21 | "If this table changes" lists dependants | Map, Data model | Gold tables and dashboards listed |
| 22 | Studio: Talk to Lumen places a tile | Studio | Tile appears in a slot |
| 23 | Studio: Undo and History restore a step | Studio | Board matches the step |
| 24 | Studio: inspector changes chart type | Studio, This chart | Chart redraws, step added |
| 25 | Studio: drag moves a tile; corner resizes it | Studio | Snaps to slot and grid |
| 26 | Studio: three options, one pick, Use this applies | Studio | Three options; tile changes |
| 27 | Studio: checks show and one fix clears a check | Studio, Checks | Check gone after fix |
| 28 | Sketch: boxes get one status each | Studio, Sketch | Possible, needs definition or not possible |
| 29 | Teach: Leo can teach Span; Mei cannot | Settings, Teach | Span listed for Leo, not for Mei |
| 30 | Teach: a picture file is refused | Teach | Plain refusal |
| 31 | Tally answers with "Used:" after a matching note | Action, Ask Tally | Line shows the note's title |
| 32 | Testing and Real use switch and line update | Top bar | Mode and line change together |
| 33 | Settings counts match section 1.2 | Settings, each person | Counts match |
| 34 | Backend suite passes | `pytest` | No new failures |
| 35 | UI suite and typecheck pass | `vitest`, `tsc` | No new failures |

---

## 8. Known limits

Say these before a client finds them.

### 8.1 Data and figures

1. **UC8 cannot run past the first load.** Trades do not reach silver `transactions`. The trade check compares zero trades until a trade loader exists.
2. **Span's gold SQL can fail.** The product's guard refuses the word "call" and similar words. A person may need to rewrite the select.
3. **A confirmed notice can move uncalled commitment by millions.** UC6 found it in August (13.1 million against 8.9 million). Fixed after the test. Re-check it.
4. **A paid capital call can still raise a Fund-the-call case** (UC6 finding M7).
5. **October limit figures repeat September.** New valuations in the administrator file do not reach the limit check (UC5 gap G-2).
6. **No limit figure on the Consume dashboard** (UC5 gap G-1).
7. **Limit cap in force.** The seeded register said 5 percent. The signed workbook said 6 percent. The CIO decides.
8. **Standing limit breaches.** UC5 changed these to one case per standing breach, with later months added to it. Re-check this on the next run, because the change was tested on synthetic data only.
9. **No early-warning band and no estimate flag** for hedge funds in the limit check (UC5 gaps C11, C12).
10. **The trade check uses a fixed 30-day window**, not the calendar month. It cannot see amendment rows for earlier months (UC8).
11. **Daily pipeline uploads can overwrite each other.** A file is named with today's date, so many daily files uploaded on one day overwrite (UC8 finding M7).
12. **The benchmark compare ignores the entity in a label.** Correct entity figures can show as unexplained variances (UC6 finding M6).
13. **A receipt log with no portfolio does not load** (UC6 finding M5c).
14. **The benchmark sheet can be refused to the owner** (UC8 finding M3).
15. **Lineage is partial.** `run_id` is on gold tables. The bronze load ID from the market-data loader and the run ID on silver are not joined up yet.
16. **Lumen's tile proposals are not always accepted.** A tile proposed for "available cash by entity" returned "no such tile" (UC6 finding L11).
17. **The approval panel can say "No reviewed run is on record"** after a passing run (UC5 finding N-1).
18. **Operations shows the wrong actor.** Trade check runs are logged as "system", not the person who pressed Run now (UC8 finding m3).
19. **The starter dashboard is proposed once per project.** A later pipeline change does not regenerate it.
20. **No email is sent by the product.** The Morning Note email and Slack are previews only.

### 8.2 Agents

21. **North loops and invents sources.** It repeats questions and turns figures into "sources". The builder then refuses to run (UC6 finding H3, UC8 finding M2).
22. **North claims writes it did not make** in some turns (UC8 finding M1).
23. **Each North turn can take 60 to 150 seconds** in test mode (UC8 finding m4).
24. **Tally does not decide**, and it cannot change a figure.
25. **Span cannot add a new silver table.** A proposed new silver table needs a model change approved by the head of data.

### 8.3 Access and modes

26. **Only the administrator or the sponsor can switch Testing or Real use**, which is the design. Others see the switch but are refused.
27. **Owner rights in the trade check.** Mei is told that Anita, Leo or Grace can run it, but Anita and Leo are refused. Only the administrator can run it (UC8 finding M5).
28. **Sofia cannot take or close cases** in the seeded roles. The UC5 test had to make her an owner on screen.
29. **Figures to confirm are for the data team.** Mei cannot confirm extracted PDF fields.
30. **Pack open rows can be settled with any text.** Five "map this sample" rows were settled before any mapping existed (UC6 finding M8).

### 8.4 Demo and platform

31. **Daily model spend cap and a per-person chat limit** apply to the hosted demo. Do not start a new project with North live in front of a client. Show a signed intent instead.
32. **Egress and keys.** Keys are service variables, never files. The internet switch must be on for any connector test.
33. **Live pipelines show "Not run yet"** for the three file sources in the seeded demo.
34. **Market data gaps.** SGS yields are auction yields, not a daily curve. EWS stands in for the licensed Straits Times Index. SORA is not connected.
35. **The film script is out of date.** It has no scene for Map, Operations or Connect an API, and its end card says "every morning" for a monthly pack.
36. **The Operations page is shown to the administrator and the data engineer**, not to the head of data (section 1.2).
37. **Older slides and the older run sheet** may say Map's impact view or Operations is missing. Both exist now. The run sheet still lists some fixed known gaps.
38. **Owner's Action groups.** The demo data shows statements to chase and figures to confirm to Mei and Daniel. `roles.ts` hides those groups from the owner. One of them is wrong. Decide which before a demo.

---

## Appendix: figures to have in your head

Demo figures (synthetic, for talk tracks only):

| Fact | Figure |
|---|---|
| September report, as issued 3 October | USD 57,600,000 |
| Known now after the Fund A revision (7 October) | USD 57,780,000, a change of +180,000 |
| September benchmark | portfolio 4.1667 percent, benchmark 2.7072 percent, +1.4595 points |
| Entity B cash, 8 October | administrator 880,400, trading desk 868,000, difference 12,400, allowance 5,000 |
| Capital calls in 30 days (Entity B) | 450,000 (20 October, confirmed) and 600,000 (30 October, not confirmed) |
| Limit breaches (September) | Harborview 5.75 percent against 5 percent (real, over by 308,000) |
| Trade differences | Northwind 75,870; Harborview sale 592,000 missing at the administrator |
| Missing statement | Cedarpoint Opportunities II, 30 June 2026, due 14 July, 63 business days overdue |

Say "portfolio minus benchmark, in percentage points". Never explain a figure you cannot trace.

---

## 9. Where things are

- Feature coverage: `docs/demo/COVERAGE.md`
- Demo data by screen: `docs/demo/DEMO-DATA.md`
- Run sheet for live shows: `docs/demo/showcase/RUN-SHEET.md`
- Full user guide (25 pages, older): `docs/guides/USER-GUIDE.md`
- Use-case guide: `docs/guides/DEMO-GUIDE-10UC.md`
- Studio plan and cards: `docs/plan/v6-landings/STUDIO2-CARDS.md` (screenshots `studio2-*.png` in the same folder)
- Teach the agents plan: `docs/plan/v6-landings/TEACH1-teach-an-agent.md`
- Live test plans, runbooks and reports: `docs/test/uc-live/`
- Role table: `ui/src/shell/roles.ts`
- Test-deck slide texts: `docs/demo/testing-deck/build_deck.py`
