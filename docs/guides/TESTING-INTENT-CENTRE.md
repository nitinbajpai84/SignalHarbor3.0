# Testing Signal Harbor: comprehensive hand-testing guide

**Date:** 7 October 2026  
**Servers:** App and backend http://127.0.0.1:8200 (the built app, for the demo) · vite dev server http://localhost:8201 (development)  
**Demo company:** ardmore (synthetic, family office)  
**Theme:** dark (default)  
All passwords live in `data/_control/seed_credentials.txt`, never printed.

---

## Sign-in and the five test accounts

Five accounts sign you into the demo company:

| Account | Email | Role |
|---------|-------|------|
| Organiser (Janet) | `company_admin.ardmore@example.test` | company_admin |
| Sponsor (Daniel) | `sponsor.ardmore@example.test` | sponsor |
| Analyst (Katie) | `analyst.ardmore@example.test` | analyst |
| Participant (Aaron) | `participant.ardmore@example.test` | participant |
| Owner (Harvey) | `owner.ardmore@example.test` | owner |

Plus:
- **Approver (Grace):** `approver.ardmore@example.test` (approver role, sees Pulse and Consume)
- **Super admin:** `platform@example.test` (controls all companies, never company data)

Start each browser window with theme set to dark. Watch that each role sees only its allowed centre links in the top bar.

---

## Screens in test order (the demo script flow)

### 1. Sign-in page (`/`)

**What must be there**
- Theme choice: Light, Dark, Match my device (dark is default)
- Email and password fields
- Sign-in button

**To test**
1. Reload http://localhost:8201
2. Confirm the sign-in page appears with theme choice visible
3. Theme choice persists on reload

**Acceptable not available yet**
- Federated sign-in (SSO)

---

### 2. Pulse (`/centre/pulse`)

**What must be there (all roles)**
- Greeting line: "Good morning, [name]"
- Five card groups: invited actions, definitions to confirm, files requested, measures owned, market context, map card, memory card
- Top bar links match the role's access
- Avatar menu (top right): Control panel (admin only), Memory, Register, Settings, Sign out

**Organiser (Janet) sees**
- Sponsor request to start Treasury wall with drafted session
- Treasury wall listing who has not written
- Performance wall running
- Owners waiting for input
- Quarter's outcome counters (sessions, walls, clusters, governed, trials)

**Sponsor (Daniel) sees**
- Charter to sign
- Two measure confirmations
- One-line purpose to write
- Initiatives table with hurdles
- Watch (market) statistics

**Analyst (Katie) sees**
- Ops report today (on time, late, failed)
- Blueprint to sign
- Invite as data voice
- Room detail lists

**Participant (Aaron) sees**
- Invite to Performance wall
- Cards for that wall (his drafts prefilled from interview)
- Measures he owns
- Market context one card
- Map and memory

**Owner (Harvey) sees**
- Similar to participant (no wall edit, no Build)

**What to click**
1. One of the action cards (e.g., the wall invite) → opens the relevant screen
2. Avatar menu → Control panel (organiser only), Memory, Register, legacy
3. Top bar links → navigates to that centre

**What must happen**
- Click an action card → that screen loads with the right context
- Signed-out message appears if session expires
- Scroll down to see all cards (no truncation on 1280px width)

**Not available yet**
- Email sending (drafts kept at `/api/pulse/messages`, Send returns 503)
- Agents do not write memory yet (starts empty, only you can correct it)
- Blueprint link appears on organiser pulse only when a signed baseline exists
- Wall link shows only open walls, not closed ones

---

### 3. How my organisation connects (`/centre/intent/graph`)

**What must be there**
- Five-column map: Problem, Measure, Driver, Team, Release
- Hover one measure → relationship trail highlights (gold line shows the trace)
- Click one measure (e.g., Trust NAV) → opens the node page
- Every node is clickable, none are dead

**To test**
1. Sign in as any role (graph is public to everyone)
2. Hover over a measure title
3. Click that measure
4. Watch the trail light up on hover

**What must happen**
- Clicked measure opens the node page with its definition, owner, dates, comments, versions
- Relationship lines are visible and follow the data flow

**Not available yet**
- Graph view as a 3D model (link exists in the definition section; not built)

---

### 4. One thing on the map: node page (`/centre/intent/map/<node_id>`)

**What must be there**
- Two-column layout: left side shows definition and ownership, right side shows the trail and versions
- Teal heading with node type (Measure, Problem, Cluster, etc.)
- Owner name, dates (created, released, next review)
- Comments section: every comment with timestamp, who wrote it, edit/delete if yours
- Versions list: every signed version with date, person, changes
- Trail (five steps from Problem → Measure → Driver → Pipeline → Release) with all links live

**To test**
1. Click one measure from the map
2. Read the full definition (left column)
3. Scroll to Comments → add a test comment
4. Click a version in the Versions list
5. Click a step in the Trail to navigate

**What must happen**
- Definition shows owner, status, source (where it came from: the wall, the interview, import)
- Comments display relative time ("2 hours ago"), not absolute time
- Click a version → that version's content appears with a byline
- Click a trail step → jumps to that node in the map

**Not available yet**
- Versions may be sparse if the baseline or blueprint were never signed
- No measure owns a pipeline yet (Build home blueprint not signed)
- Comments may show "Not available yet" if the node has none

---

### 5. Intent centre home (`/centre/intent`)

**Organiser (Janet) sees**
- Three room cards lit in order: "Bring what you have" → "The wall" → "Define"
- Live count on each
- Governed state panel (either "Not available yet" on empty profile, or the four percentages: owners stated, classified, published, team assigned)
- Nira's first three waiting items
- Four counters: this week's sessions run, cards on walls, clusters defined, measures governed

**Sponsor (Daniel) sees**
- Same rooms, read-only (cannot open Bring or The wall unless invited by link)

**Participant (Aaron) sees**
- Only "The wall" link (unless invited to specific walls)
- Pulse link takes precedence

**What must be there**
- Three room tiles with state (not available, in progress, complete)
- The governed bar shows: "Not available yet" if no profile loaded, or four percentages
- Waiting list card shows Nira's next three items (or empty if nothing pending)
- Four outcome counters, each with "Not available yet" if no data

**To test**
1. Sign in as organiser
2. Read the three room titles and counts
3. Look at the governed state panel
4. Click "Bring what you have" → opens the bring screen
5. Back to home → check counts update

**What must happen**
- Switching centre off (super admin, entitlements.json `centres: {intent: false}`) hides all three rooms
- Numbers always trace to records; never show 0 when there is no data
- Counts update after you complete an action (usually within 2 seconds)

**Not available yet**
- Profile grouped by topic (the grouped Define view)
- Outcome grid (counts work; the full chart does not)

---

### 6. The wall (`/centre/intent/wall/<session_id>`)

#### Layout

**Organiser (Janet) sees**
- Four lanes: North (his questions), East (opportunities), South (constraints), West (assets) spread across full width
- North's panel on the right (420px, sticky): current question highlighted, four quarter bars (fills per lane), conversation thread, your answer box
- Stage bar above all lanes (lit stages, one next-step button)
- Invite panel (join link, seats taken, revoke, generate new link)
- "What we are here for" line with purpose, topic chip (if set), initials of named contributors

**Participant (Aaron) sees**
- Four lanes (or 1 on phone)
- Join link opens his private room
- Suggestion cards (dashed, "Suggested by North"): click "Pick it up" → card moves to the lane
- Anonymous cards show no name
- Sealed cards show "Sealed" to anyone outside the restricted area

**What must be there**
- Four lanes with equal height, left edge filling by quarters (0, 25, 50, 75% fill)
- Card count per lane
- Participant initials on each card (no names on anonymous, no card content on sealed)
- North's panel with four numbered questions (or fewer if already answered)
- Stage bar with lit stages, one "Next step" or "Start" button
- Invite panel with a copyable join link
- Each card is clickable to read and edit (if yours)

**To test as organiser (Janet)**
1. Open the Treasury wall (started by sponsor request)
2. Count the cards in each lane
3. Look for "Put it on the wall now" button (appears after 2+ questions answered)
4. Move one cluster to a different shelf (if this is the Define screen)
5. Click stage bar → stages light, button changes text
6. Click "Next step" when a stage is complete

**To test as participant (Aaron)**
1. Paste the join link in a new private window
2. You land on your private room with North's first question
3. Read the drafts (prefilled from your interview if you took one)
4. Add or confirm a card
5. Mark it anonymous (checkbox in the card form)
6. Back to the wall → your card appears
7. Click a suggestion card → "Pick it up" button adds it to the lane
8. Check "Sealed" checkbox if you mark content about people, pay or personal data

**What must happen**
- Lanes show equal count or one off (e.g., 5, 5, 5, 4)
- Each lane fills proportionally as cards are added
- Your own sealed notes show as "Sealed" to anyone outside the area
- Suggestion cards (dashed outline) have a "Pick it up" button; clicking moves the card to the lane
- North groups the board by topic if multiple walls are open (feature not built yet)

**Phone (390px width)**
- One lane at a time (swipe or tap lane buttons to change)
- Projector view (full screen, lanes and counts only, no names or content)

**Not available yet**
- Wall window (setting `wall_window_days` to auto-freeze after N working days)
- Grouped Define by topic (requires multiple walls; feature not built yet)

---

### 7. Charter and "Who does what" (`/centre/intent/charter/<session_id>`)

**What must be there**
- Six problems listed with "so that" lines (intent and benefit)
- Who took part (names or anonymous)
- Signature line (date, signatory name)
- Download button (exports to PDF with all problems, answers, "Who does what" table)
- "Who does what" section: six Build roles (owner, architect, builder, tester, releaser, analyst liaison), drafted from the people in the wall, editable by organiser
- Status: draft, signed, or superseded

**To test as organiser (Janet)**
1. Open the wall → click "Move to together" or similar to go to charter
2. Read the six problems and "so that" lines
3. Click "Who does what" panel
4. Edit one role: click the name, change it, confirm
5. Download the charter
6. Compare with the PDF

**To test as sponsor (Daniel)**
1. Open the same charter
2. Try to edit a role name (should not be allowed)
3. Read the signature section
4. Click "Sign the charter"
5. Confirm you are the sponsor (modal check)
6. Watch the signature update with date and your name

**What must happen**
- Problems show exactly as entered in the wall (no grouping yet)
- "Who does what" shows only named people (no blank rows)
- Edit saves immediately (no Save button)
- Sign button asks "Are you [sponsor]?" before committing
- Download opens a PDF with proper formatting (check text is not cut off at 390px)

**Not available yet**
- Charter version history (only current version shown)
- Parked clusters (Future shelf) listed under "Parked for later" with reason

---

### 8. Define (`/centre/intent/define/<session_id>`)

**What must be there**
- Four shelves (Must, Should, Good to have, Future) with clusters dragged between them
- Each cluster shows: colour, card count, votes, measure codes, governed ring (dashed until all measures confirmed)
- Right panel: Lens's definition for selected cluster, six fields per measure (owner stated/guessed, classification, who may see, team, review date, affects), "Confirm the definition" and "Send back with a note" buttons
- Governed block showing the four percentages: owners, classification, published, team assigned

**Organiser (Janet) sees**
- Full edit: drag clusters, "Confirm the definition" calls Lens to update module 2

**Sponsor (Daniel) sees**
- Read-only view
- Can click "Send back with a note" to return a measure to Lens

**To test as organiser**
1. Open Define on a closed wall (Treasury wall is closed and defined)
2. Click one cluster → right panel shows Lens's proposal
3. Click "Confirm the definition" → Lens updates
4. Try to move an ungoverned cluster to Must (should be refused with a message naming what is missing)
5. Drag a cluster to Future → modal asks for a reason and review date
6. Close the modal → reason is kept

**To test the governed ring**
1. Each cluster has a ring (solid when all measures are governed, dashed when not)
2. Solid ring means: for every measure in the cluster, owners are named, classification is set, publication list is named, team is named, review date is set

**What must happen**
- Drag and drop updates the shelf (visual feedback: cluster moves and the ring updates)
- Confirmed definition calls the Lens agent and returns within 5 seconds
- Ungoverned cluster cannot move to Must or Should (rule A-054)
- Future cluster must have a reason and review date (modal does not close until both are set)
- Each cluster's colour is stable (survives regrouping)

**Not available yet**
- Grouped Define by topic (only one wall per company so far; feature not built)

---

### 9. Baseline and sign-off (`/centre/intent/baseline/<baseline_id>`)

**What must be there**
- Measures (from the clusters) listed with status (draft, confirmed, signed)
- Click one measure → panel expands showing: definition, owner, classification, who may see, resolving team, review date, affects
- Gate: "Has the sponsor signed the charter?" (must be yes before you can confirm)
- Signature line: "Sponsor sign", showing date and name if signed, or "Not signed yet"
- Sign-off panel: "Who must sign? Sponsor" (or more if configured)
- Send back button with text area for a note

**Owner (Harvey) or Approver (Grace) sees**
1. Open a measure (by invite link or from Pulse)
2. Read the definition
3. Click "Confirm" (confirm that you agree with the definition and status)

**Sponsor (Daniel) sees**
1. Same view as owner
2. Also sees "Sign off the baseline" button
3. Click it → asks for confirmation (modal: "Are you the sponsor?")
4. Watch the signature update

**To test**
1. Sign in as owner
2. Navigate to one of the baselines (from Pulse → "Confirm definitions")
3. Click one measure
4. Read the panel
5. Click Confirm
6. Back to list → that measure shows "Confirmed"
7. As sponsor: click "Sign off the baseline" → signature appears
8. Try to click "Send back" with no text (button should be disabled)
9. Add a note, click Send back → measure returns to draft

**What must happen**
- Gate check: you cannot confirm until sponsor has signed the charter (gate message appears red if not met)
- Confirm button changes to "Confirmed ✓" (or similar visual)
- Send back with a note resets the measure to draft and notifies the owner
- Signature persists after page reload

**Not available yet**
- Baseline version history (only current version)
- Multiple signatories per baseline (only sponsor for now)

---

### 10. Moment of truth and data request (`/centre/intent/truth/<assessment_id>`)

**What must be there**
- Scoreboard (three tiles: MATCH, GAP, NOT YET with counts)
- Source map (left side: five columns like the main map)
- Trial table (measures in rows, status pills: match, gap, not yet, proposed fix in amber)
- Plan in three bands: the gap, the fix, how to know we are right
- Signature panel (bottom): who must sign (owner, analyst, sponsor), Sign button, Upload button

**Organiser or Owner sees by invite link**
1. Click "Upload sample" (or "Upload files")
2. Select a CSV matching the source pattern
3. Watch the Run log update
4. See Lens's quality rules in the trial table (e.g., "Fees Charged must be non-empty; 20 of 40 empty in the September sample")

**Analyst (Katie) sees**
1. Same view, can sign off
2. Sees "The plan" with the team and review date

**To test**
1. As owner: click the upload zone
2. Select a small test CSV (matching the source pattern, e.g., `accountant-input-*.csv` for the custodian file)
3. Watch the log update (run time, status)
4. Scroll down → trial table updates with new rows and quality rules
5. Click one rule (e.g., "non-empty") → see the breakdown (20 empty, 20 filled)
6. Try to sign without uploading (button may be disabled if required)

**What must happen**
- Upload zone accepts a file matching the source pattern (refuse others with a clear message)
- Run log shows: start time, end time, status (OK, FAILED, LATE), rows processed
- Quality rules appear with examples (must not be all technical; use plain language)
- Restricted sources hide rules from anyone outside the list
- Sign button is disabled until both owner and analyst confirm

**Not available yet**
- Email notifications (drafts kept at `/api/pulse/messages`)
- Baseline required: blueprint cannot be signed without a signed baseline (error message explains this)

---

### 11. Build centre home (`/centre/build`)

**Analyst (Katie) and Organiser (Janet) see**

- Three room tiles: Environment, Blueprint, Pipelines (lights show state: not started, in progress, complete)
- Environment: five questions with status (confirmed, draft, or "Not started")
- Blueprint: drafted from the signed baseline; says "No blueprint yet" if baseline not signed
- Pipelines: one card per source, Run now button, six months of run history in a log
- Prove and release: Matches, gaps, UAT and release status
- Ops: today's arrivals, failed checks, range breaks, alerts with a drafted ask, run book

**What must be there (all screens)**
- Room tiles lit by state
- No link to orphaned sources (sources without a signed baseline are not shown)
- Data never truncated or summarized wrongly (always show "Not available yet" if source is missing)

**To test**
1. Sign in as analyst
2. Look at the three rooms
3. Count the number of pipelines shown
4. Click one pipeline card → opens Pipelines screen

**What must happen**
- Environment shows five questions; click one → field appears for edit
- Confirm each question (no Save button; confirmation is immediate)
- Blueprint shows "No blueprint yet" or the facts and dimensions table
- Pipelines shows at least six months of history (even if all runs were today, show 180+ days of potential)
- Room tiles light based on the state of the data, not a hardcoded schedule

**Not available yet**
- Data flow: drop a CSV and press Run (Pipelines screen feature, works if file matches pattern)

---

### 12. Environment (`/centre/build/environment`)

**What must be there**
- Five questions (topics: scope, frequency, quality gates, team skills, review cycle)
- Each question shows: title, description, current answer (or empty), Confirmed or Draft pill
- Click one → edit panel opens inline
- Confirm button (becomes "Confirmed ✓")
- Never a Save button (changes commit on Confirm)

**To test**
1. Click one question
2. Read the description
3. Enter an answer in the edit field
4. Click Confirm
5. Watch the pill change to "Confirmed"
6. Reload the page
7. Answer persists

**What must happen**
- Edit panel shows in place (not a modal)
- Confirm is disabled until you edit
- Each answer is independent (confirming one does not commit others)
- No Save button; Confirm commits the answer

**Not available yet**
- None (this is a simple form)

---

### 13. Blueprint (`/centre/build/blueprint`)

**What must be there**
- Title: "Blueprint" (or "No blueprint yet" if baseline not signed)
- Facts table: one row per fact with owner, classification, who may see, team, review date, affects
- Dimensions table: one row per driver dimension
- Each row shows: name, type (fact or dimension), status mark (stated/guessed), source
- Sign-off panel: who must sign (architect, analyst, tester), date, signatures

**To test**
1. Open the blueprint (from Build home)
2. Count the rows in Facts and Dimensions
3. Read one row → tooltip shows the source (e.g., "From the wall, 15 Sep")
4. Click the sign-off panel
5. As architect or analyst: click Sign

**What must happen**
- Blueprint cannot be signed before the baseline is signed (message explains this)
- Every name and mark must be traceable to a record
- Each signature persists (check the date is today's)
- If blueprint is not signed yet, sign-off panel shows "Not signed" for each role

**Not available yet**
- Versions (only current blueprint shown)
- Edit mode (blueprint is read-only; changes come from Lens in the Define screen)

---

### 14. Pipelines (`/centre/build/pipelines`)

**What must be there**
- One card per data source (e.g., "Custodian file", "Accounting export")
- Each card shows: source name, last run date and status (on time, late, failed), Run now button
- Run log below: one row per run in the last 180 days with: start time, end time, status, rows processed
- Drop zone: drag a CSV matching the source pattern and drop it on the card

**To test**
1. Open Pipelines
2. Count the source cards
3. Click one Run now button → log updates (watch for network activity)
4. In your OS file manager, navigate to the company landing zone (e.g., `data/ardmore/landing/`)
5. Create a CSV named like the source pattern (e.g., `custodian-input-20261007.csv`)
6. Back to the app: drop the file on the source card
7. Watch the log update with a new run

**What must happen**
- Run now triggers a pipeline run (log updates within 5 seconds)
- Status is shown as Pill: ok (green), late (amber), failed (red)
- Dropped file starts a run if the name matches the pattern (refuse with a message if not)
- Log shows only the last 180 days (scroll down to see older runs if any)

**Not available yet**
- Retry button for failed runs
- Live run progress (shows only completed runs)

---

### 15. Prove and release (`/centre/build/prove`)

**What must be there**
- Three sections: Matches, Gaps, Not yet
- Each section lists measures with a status (Match, Gap, Not yet, Plan, Done)
- For each measure: owner, pipeline, source, the gap (e.g., "5% margin below forecast")
- Accept gap button: click it → panel shows reason (e.g., "Data is 2 months late"), confirm
- Sign UAT panel (tester signs), Release panel (sponsor signs)

**Organiser or Analyst sees**
1. Open Prove and release
2. Count measures in each section
3. Click one gap measure → panel shows the gap detail
4. Click "Accept this gap" → reason and date appear
5. Confirm it → measure moves to Done

**Sponsor sees**
1. Same view
2. Also sees Sign UAT button (tester signs; you cannot)
3. Click Release → modal asks "Are you releasing?" and lists all measures
4. Confirm → release persists (date, your name)

**To test**
1. Open the screen
2. Click one measure in Gaps
3. Accept the gap (reason auto-filled if available, or you add one)
4. Watch it move to Done
5. Count the measures in each section (should total the number of measures in the baseline)

**What must happen**
- Clicking a gap measure shows the full gap (not truncated)
- Accept gap asks for a reason (radio buttons or text input based on the situation)
- Release requires sponsor sign-off (button disabled if not signed)
- All measures must be addressed (Match, Gap accepted, or Not yet) before release

**Not available yet**
- Not yet measures can be released (feature not complete; they must be addressed)

---

### 16. Ops (`/centre/build/ops`)

**What must be there**
- Today's arrivals: data that landed since yesterday midnight (count, sources)
- Failed checks: rules broken (e.g., "non-empty field had 20 empty values")
- Range breaks: a measure outside its usual range (e.g., K02 "outside range in September")
- Alerts: drafted by Watcher agent, one per issue, with an Acknowledge button and optional note

**To test**
1. Open Ops
2. Read the arrivals count (must trace to landing zone file count)
3. Click a failed check → shows the rule and the measure it applies to
4. Click a range break → shows the measure name, the range, the breach (e.g., "Sep 15: 45.2%, outside range 30–42%")
5. Click an alert → Acknowledge panel shows, add an optional note
6. Click Acknowledge → alert status changes to "Acknowledged"

**What must happen**
- Arrivals count matches the number of files in the landing zone
- Failed checks never show restricted areas (hide them with count only: "3 alerts in restricted areas")
- Range breaks show the measure, the expected range, and the breach (not the raw value)
- Alerts persist after reload (check the Acknowledged status)

**Not available yet**
- Run book (link exists, page not built)
- Automated remediation (suggested actions are drafted but not executable from here)

---

### 17. Consume centre home (`/centre/consume`)

**Sponsor (Daniel), Owner (Harvey), Approver (Grace) see**

- Three room tiles: Feeds, Market forces, What-if
- Nira's top three waiting items
- Four counters: measures released, within range, outside range, watchers assigned

**To test**
1. Sign in as sponsor
2. Look at the three rooms
3. Count the measures released (must trace to the signed baseline with approved blueprints)
4. Read the three waiting items

**What must happen**
- Each counter is a clickable link to the relevant list
- Counters show "Not available yet" if no data
- Never show 0 if there is actually no data (distinction matters)

**Not available yet**
- Measures per centre (Consume breadcrumb not working yet if no measures exist)

---

### 18. Feeds (`/centre/consume/feeds`)

**What must be there**
- One card per released measure
- Each card shows: measure name, latest value, status (in range, outside range), sparkline (last 30 days), owner, "Go to the measure" link
- Outside range measures shown in amber (highlight, e.g., K02 "outside range in September")
- On the demo company: twelve measures are seeded in the warehouse (April–September 2026)

**To test**
1. Open Feeds
2. Count the measure cards (should be at least 12 on demo company)
3. Look for K02 (outside range) in amber
4. Click K02 card → opens the measure page (see below)
5. Scroll through sparklines (each shows 30 points, one per day)

**What must happen**
- Every measure traces to a warehouse record (value, date, pipeline, source)
- Sparkline shows the last 30 daily values (or "Not available yet" if fewer than 3 data points)
- Owner is the person assigned in the baseline
- "Outside range" means the latest value breaches the range set in the baseline

**Not available yet**
- Forecast comparison (planned but not built)
- Alerts linked to measures (alerts exist in Ops, but feeds does not show them yet)

---

### 19. Measure page (`/centre/consume/measure/<measure_id>`)

**What must be there**
- Teal heading with measure name and type (KPI, metric, output)
- Latest value, date, status (in or outside range)
- Full line chart: all available historical values (9 months on demo company, April–September)
- Definition panel: owner, classification, who may see, team, review date, pipeline
- Links to the map, the blueprint, the assessed quality rules
- Comments section (read-only for most roles; owner or steward can add)
- Versions list (if any blueprint updates)

**To test**
1. From Feeds, click K02
2. Read the chart (should show 9 months of points)
3. Look at the definition panel (left side)
4. Scroll to Comments → try to add a test comment (may not be allowed if not owner)
5. Click the map link → jumps to the node page for this measure

**What must happen**
- Chart is interactive: hover to see the value and date
- Latest value is highlighted (usually amber or green on the chart)
- All links are live (map, blueprint, quality rules)
- Comments show who wrote them and the relative time

**Not available yet**
- Forecast line on chart (planned)
- Edit definition (changes only through Define → Baseline → Moment of truth flow)

---

### 20. Market forces (`/centre/consume/market`)

**What must be there**
- The pack brief card (marked "Outside material") next to a list of measures that the brief mentions or touches
- Brief title, date, source (e.g., "Family office survey Q3", marked as outside material)
- Each measure touched by the brief is listed (clickable to the measure page)

**To test**
1. Open Market forces
2. Read the brief title and source
3. Count the measures listed below it (must trace to Lens's analysis of the brief)
4. Click one measure → opens that measure's page

**What must happen**
- Brief is always marked "Outside material" (not a company record)
- Only measures defined in the company are listed (no invented measures)
- Brief is never the source of a company's figures (it is context for decisions)

**Not available yet**
- Multiple briefs (only one loaded on demo company)
- Brief full text (only title and source shown for now)

---

### 21. What-if (`/centre/consume/whatif`)

**What must be there**
- Driver slider: a dimension that moves (e.g., "Fees Charged" from −10% to +10%)
- Map below showing measures that move as the slider moves (coloured highlight shows impact: green if moved in a good direction)
- Scenario save button: keep a scenario and name it
- Scenario list: all saved scenarios for the company

**To test**
1. Open What-if
2. Find the slider (e.g., "Fees Charged")
3. Move it to +10%
4. Watch the map update (some measures should highlight)
5. Type a scenario name (e.g., "Fees up 10%") and click Save scenario
6. Reload the page
7. Your scenario appears in the scenario list (click it to restore the slider position)

**What must happen**
- Slider moves smoothly (0.5 second update lag acceptable)
- Map impact is computed and highlighted (measures that move are shown in colour, others in grey)
- Scenario saves with a name and timestamp
- Scenario list persists (reload check)

**Not available yet**
- Multiple drivers (only one slider implemented)
- Scenario sharing (scenarios are per user for now)
- What-if historical comparison (what actually happened vs. the scenario)

---

### 22. Register (`/centre/register`)

**What must be there**
- One row per released measure
- Columns: Measure name, Owner, Pipeline, Five signatures (charter, baseline, blueprint, UAT, release) each with date and name, Version
- Measures are sorted by release date (newest first)
- No truncation at 390px width (table scrolls horizontally or switches to card layout)

**To test**
1. Open Register
2. Count the measures (should match the number released in the baseline)
3. Look at one measure's signatures (all five must be filled)
4. Click a signature → tooltip shows date and name
5. On mobile (390px): table should adapt (switch to cards or scroll)

**What must happen**
- Every signature date is today or a previous date (never future)
- Every signature name matches a real person in the company
- Table is readable at 1280 and 390 (no text cut off)
- Register is read-only (no edit)

**Not available yet**
- Measure history (only current signatures shown)
- Export to CSV (download button exists but not built)

---

### 23. Memory (`/centre/memory`)

**What must be there**
- Empty by default (until a conversation ends, the agents do not write memory yet)
- Store filter: "All", "My memory", "Company memory"
- Routes filter: "All", "Define", "Moment of truth", etc.
- List of memories (if any)
- Each memory shows: topic, date created, last updated, who it concerns, "Edit" link (if yours)

**To test**
1. Open Memory (as any role)
2. Look for the two filters (Store and Routes)
3. Try each filter combination (should return empty or the same list)
4. If there are any memories (from a prior conversation), click one
5. Read the entry
6. If it is yours, try to edit (click "Edit" → text field appears)
7. Type a correction → Save

**What must happen**
- Page loads quickly (empty or with data)
- Filters are independent (Store and Routes both filter)
- Correction is saved immediately (no modal)
- Correction timestamp updates

**Not available yet**
- Agents writing memory (Nira, North, Lens, Architect, Builder, Prover, Watcher do not write memory yet)
- Memory export

---

### 24. Control panel (`/centre/control`)

**Super admin sees**
- Company list: all companies with entitlements and status
- Create company button: name field, industry pack chooser
- For each company: view, switch centre (Intent, Build, Consume) on/off, switch module (M1, M2, M3) on/off
- Provider list: MCP tools, cloud push settings, API key management

**Company admin sees**
- Egress settings: Internet (on/off toggle, with "off by default" note), Connectors list, Cloud push (requested or active), Download egress log
- Egress log: all outbound calls with: timestamp, type (query, tool, egress), target (URL or tool name), status, response time
- Log entries never show payload (data never sent; privacy first)

**To test as super admin**
1. Sign in as platform@example.test
2. Open Control panel
3. Find the ardmore company in the list
4. Click it → details panel shows
5. Toggle Intent centre off → reload the home page as company_admin.ardmore
6. Three rooms should disappear from Intent home
7. Back to control panel, toggle Intent back on
8. Reload as company admin → rooms reappear

**To test as company admin (Janet)**
1. Open Control panel
2. Look at Egress settings (Internet toggle)
3. Click Download egress log
4. Open the CSV (never shows credentials or full payloads)

**What must happen**
- Centre and module switches persist after reload
- Switching off a centre hides all its screens from the navigation bar and removes the routes
- Log download is a CSV with seven columns (timestamp, type, target, status, response time, request size, response size)

**Not available yet**
- Email domain allowlist editing (control panel screen built, UI not wired)
- Audit log (egress log is the first audit log)

---

### 25. Top bar navigation

**All roles see**
- Company name (left side)
- Links to each accessible centre (Pulse, Intent Centre, Consume, Map, Build if analyst/admin)
- Control Panel link (admin only)
- Avatar menu (right side: Memory, Register, Settings, Help (not built), Sign out, Control Panel for admin)

**To test**
1. Sign in as participant → see "Pulse", "Map" only (no Intent, Build, Consume)
2. Sign in as sponsor → see "Pulse", "Intent Centre", "Consume", "Map" (no Build)
3. Sign in as analyst → see all (Pulse, Intent Centre, Build Centre, Consume, Map, Control)
4. Click avatar → menu appears with your role, Memory, Register, Settings, Sign out, Control for admin
5. Click Settings → settings page loads (theme, language if available)

**What must happen**
- Links match the role table (QUALITY-PASS.md section 1)
- Avatar menu closes when you click away
- Clicking a centre link navigates to that centre's home page
- Control Panel is hidden for non-admin roles

**Not available yet**
- Help link (marked "Coming soon" if present)

---

### 26. Theme persistence

**To test**
1. On the sign-in page, set theme to Light
2. Sign in
3. Reload the app → theme persists (Light)
4. Sign out
5. Sign in again → theme is still Light

**What must happen**
- Light theme shows: light background, dark text, muted colours
- Dark theme shows: dark background, light text (ink and ink-soft), teal accents
- Match my device uses the OS preference (usually dark after 18:00)
- Theme choice persists across sessions (stored locally or in user settings)

**Not available yet**
- None (theme is working)

---

## Automated checks

### Unit tests by area

Run these before committing any changes. Each unit test covers one feature and should pass on its own.

**Backend (API and agents)**

```bash
cd "<2.0 repo>"

# Auth and permissions
.venv/Scripts/python -m pytest -q tests/auth/test_role_matrix.py
.venv/Scripts/python -m pytest -q tests/auth/test_role_table.py
.venv/Scripts/python -m pytest -q tests/auth/test_auth.py

# Intent centre
.venv/Scripts/python -m pytest -q tests/intent/ -k "not e2e"

# Build centre
.venv/Scripts/python -m pytest -q tests/build/

# Consume centre
.venv/Scripts/python -m pytest -q tests/consume/

# Contracts (API shape expectations)
.venv/Scripts/python -m pytest -q tests/contracts/test_shapes_ardmore.py

# Copy audit (no game words, vendor names, em-dashes, American spelling)
.venv/Scripts/python -m pytest -q tests/ui_audit/test_copy_rules.py

# Agent context and tools
.venv/Scripts/python -m pytest -q tests/agents/test_agents_context.py
.venv/Scripts/python -m pytest -q tests/agents/test_agents_registry.py

# Tools
.venv/Scripts/python -m pytest -q tests/tools/ -k "not seed"
```

**Frontend (React and TypeScript)**

```bash
cd "<2.0 repo>/ui"

# Type check only (no runtime)
npx tsc --noEmit

# Unit tests for a specific screen
npx vitest run src/pages/PulsePage.test.tsx
npx vitest run src/pages/WallPage.test.tsx
npx vitest run src/pages/DefineScreen.test.tsx

# All UI tests (slow, run at the end)
npx vitest run --pool=threads --maxWorkers=4
```

### Link and copy crawler

The crawler checks that:
- No link points to `/modules`, `/legacy`, or old `/company` screens
- No game words ("quest", "level", "player", "badge") in the audited copy
- No vendor or model names in copy
- No em-dashes in copy (British style: use dash with spaces or hyphen)
- No American spellings (organisation, not organization)

```bash
cd "<2.0 repo>"

# Crawl all roles over the app, starting from /centre/pulse, following links up to depth 4
.venv/Scripts/python .sh-tmp/x3-crawl.py

# Check the report
cat .sh-tmp/x3-crawl-report.json | more

# Re-run for participant role (usually not crawled in the full run)
# Open a private window, paste the join link from one of the walls, take a screenshot
# Check that the participant lands on the wall, not an old screen
```

### Full test suites (run once, at the end)

Run these only after all features are built and screenshot-tested. They take 20–30 minutes.

```bash
cd "<2.0 repo>"

# Full backend suite (all tests, 14 workers, about 15 minutes)
$env:PYTHONHASHSEED=0
.venv/Scripts/python -m pytest -n 14 tests modules --tb=short

# Full frontend suite (all UI tests, 4 workers, about 10 minutes)
cd ui
npx vitest run --pool=threads --maxWorkers=4 --reporter=verbose
```

### Health check

Before running a demo:

```bash
# Check the backend is alive
curl -s http://127.0.0.1:8200/api/health

# Check the UI is responding
curl -s http://localhost:8201 | grep -o "<title>.*</title>"

# Sign in as each of the five roles and check the top bar is correct
.venv/Scripts/python .sh-tmp/shot.py company_admin.ardmore@example.test centre/pulse .sh-tmp/shots/health-admin.png --width 1280
.venv/Scripts/python .sh-tmp/shot.py sponsor.ardmore@example.test centre/pulse .sh-tmp/shots/health-sponsor.png --width 1280
.venv/Scripts/python .sh-tmp/shot.py analyst.ardmore@example.test centre/pulse .sh-tmp/shots/health-analyst.png --width 1280
.venv/Scripts/python .sh-tmp/shot.py participant.ardmore@example.test centre/pulse .sh-tmp/shots/health-participant.png --width 1280
.venv/Scripts/python .sh-tmp/shot.py owner.ardmore@example.test centre/pulse .sh-tmp/shots/health-owner.png --width 1280

# Spot-check one role's top bar links
# Admin should see: Pulse, Intent Centre, Build Centre, Consume, Map, Control
# Sponsor should see: Pulse, Intent Centre, Consume, Map (no Build, no Control)
# Participant should see: Pulse, Map (no Intent, Build, Consume, Control)
```

---

## Reseeding the demo company

If the data is stale or you want a fresh start for the demo, run `bash .sh-tmp/s1-reseed.sh` from the repo root with the backend up (about five minutes). It runs the three seed tools below in order and then the in-place patches that give the demo its names, owners, dates, access lists, cluster joins and Aaron Lyle's drafted cards. The three tools alone leave those out. Each tool uses `--reset` or removes its own earlier output first.

### Step 1: Journey seed (creates the intent work)

```bash
cd "<2.0 repo>"
.venv/Scripts/python tools/seed_demo_journey.py ardmore --reset
```

**What this creates:**
- Two walls (Treasury and Performance, one open, one closed)
- Treasury wall: six problems with "so that" lines, thirty-nine signed cards, 1 sealed card
- Performance wall: four opening lines, participants' cards, North's suggestions (dashed cards)
- Charter: signed by sponsor (Daniel Kerr)
- Baseline: measures with status, signed by sponsor
- Assessment (Moment of truth): uploading sample data, quality rules
- Comments: six comments on measures
- Definitions: per measure, with ownership and classification

**Manifest to check** (after the run, check these files exist):
- `data/ardmore/context/walls/wall-*.json` (two walls)
- `data/ardmore/context/charters/charter-*.json` (one charter)
- `data/ardmore/context/baselines/baseline-*.json` (one baseline, signed)
- `data/ardmore/context/assessments/assessment-*.json` (one assessment)
- `data/ardmore/build/blueprint.json` (blueprint, signed)
- `data/ardmore/graph/measure-*.json` (measures with definitions)
- `data/ardmore/graph/comments.json` (six comments, keyed to measure node IDs)

**If it fails:**
- Check that ardmore exists: `ls data/ardmore/`
- Check for error messages in the output (e.g., "1 closed wall already open" means a wall on that topic already exists; delete it or run with `--reset`)
- If the error is "Assessment not found", the baseline may not have been signed; recheck the manifest

### Step 2: History seed (creates the run history)

```bash
.venv/Scripts/python tools/seed_demo_history.py ardmore --reset
```

**What this creates:**
- Six months of pipeline runs (April–September 2026, one run per month)
- Six months of alert history (acknowledged and open)
- Six months of measure versions (drafts and signed)
- Six months of memory per person

**Manifest to check:**
- `data/ardmore/build/runs/run-*.json` (26 runs total: 1 per month × 26 sources per month; only major sources shown)
- `data/ardmore/build/alerts/alert-*.json` (6 alerts, some acknowledged)
- `data/ardmore/graph/versions.json` (versions for each measure)
- `data/ardmore/context/memory/` (six files, one per person: Aaron, Janet, Marcus, Daniel, Harvey, Grace)

**If it fails:**
- Check that the journey seed ran first (blueprint and baseline must exist)
- Check for "Run already exists" error (means a run was already created; `--reset` should clear it)

### Step 3: Warehouse seed (creates the measures and history)

```bash
.venv/Scripts/python tools/seed_demo_warehouse.py ardmore
```

**What this creates:**
- Twelve released measures in the warehouse
- Nine months of historical data per measure (April–September 2026, plus forecast)
- K02 "outside its range" in September (amber on Feeds)
- Sparklines (30-day trend per measure)

**Manifest to check:**
- `data/ardmore/warehouse/*.parquet` (twelve parquet files, one per measure, 270+ rows each)
- Feeds screen shows twelve measure cards
- K02 card is in amber (outside range)

**If it fails:**
- Check that the journey seed ran first (measures must exist before you can seed values)
- Check for "Measure not found" error (means you did not run the journey seed)

### Verification

After all three seeds, verify the data is ready:

```bash
# Check that the file exists (touched when all seeds complete)
ls -la .sh-tmp/DATA-READY

# Open the app and check:
# 1. Pulse shows all the created items (walls, charter, baseline, assessment)
# 2. Feeds shows twelve measure cards, K02 in amber
# 3. Register shows twelve rows (one per measure, all signed)
# 4. Define clusters are on shelves, each with measure codes
# 5. Build home shows blueprint as signed, six months of runs in Pipelines log
```

---

## Servers

### Start the backend (if it has crashed)

```bash
cd "<2.0 repo>"

# First, check the current Python import
.venv/Scripts/python -c "import sh_platform.app; print('OK')"

# If that failed, there is a syntax error; check `.sh-tmp/backend.log`

# Start the backend. For the demo, start it plainly (no reload, so nothing can restart it and sign everyone out):
nohup .venv/Scripts/python -m uvicorn sh_platform.app:create_app --factory --host 127.0.0.1 --port 8200 > .sh-tmp/backend.log 2>&1 &
# While developing, use the watcher instead: it restarts the backend about 25 s after a Python edit
# (uvicorn's own --reload sticks after its first reload on this machine):
# nohup bash .sh-tmp/backend-watch.sh > /dev/null 2>&1 &
# The built app (cd ui && npm run build) is served by the backend on 8200 and paints in under a second; the vite dev server on 8201 is for development.

# Or on Windows PowerShell:
# Start-Process powershell -ArgumentList "-NoExit", "-Command", ".venv/Scripts/python -m uvicorn sh_platform.app:create_app --factory --host 127.0.0.1 --port 8200 --reload --reload-dir sh_platform --reload-dir modules" -RedirectStandardOutput .sh-tmp/backend.log

# Check it is listening
curl -s http://127.0.0.1:8200/api/health
```

### Start the UI (if it has crashed)

```bash
cd "<2.0 repo>/ui"

# Start Vite with hot reload
npx vite --port 8201 --host 127.0.0.1

# In another terminal, check it is responding
curl -s http://localhost:8201 | head -c 100
```

### View logs

```bash
# Backend log (last 50 lines)
tail -50 .sh-tmp/backend.log

# UI errors (in the terminal where Vite is running)
# Watch for TypeScript errors or build failures

# Browser console errors (in the app's developer tools)
# F12 in your browser → Console tab
```

### Before the demo

1. Restart both servers (kill and restart)
2. Run `python tools/doctor.py` (checks all settings and dependencies)
3. Sign in as each of the five roles and take a screenshot (see Health check above)
4. Check each screenshot against the artboards in `.sh-tmp/artboards/`
5. Open the register and verify all twelve measures are there and signed
6. Open the map and hover a measure to confirm the trail is visible
7. Close the browser windows and restart the servers one more time (fresh state for the demo)

---

## Known gaps and acceptable "Not available yet"

| Screen | Gap | Why acceptable |
|--------|-----|-----------------|
| Pulse | Email sending | No mail server configured; drafts are kept and listed |
| Intent home | Governed state | Waits for profile data from Bring and the agents' assessments |
| Wall | Topic grouping in Define | Requires multiple open walls; demo has only one or two |
| Charter | Version history | Only current version needed for the demo |
| Define | Send back to Lens | Feature works; data may not have measures that need it |
| Moment of truth | Upload by link | Feature works; tester may need to upload through the UI instead |
| Build home | Room detail lists | Ardmore has no open measures in Build; feature works, no data to show |
| Blueprint | Versions | Only current version needed for the demo |
| Pipelines | Retry button | Runs are read-only; no retries in the current version |
| Prove and release | Not yet measures | Must be addressed (matched or gap accepted) before release; none left in demo data |
| Ops | Run book | Link exists; page not built (links to a placeholder) |
| Feeds | Forecast line | Chart shows historical values; forecast not computed yet |
| Measure page | Edit definition | Changes only through the Define workflow; direct edit not allowed |
| Market forces | Multiple briefs | Only one brief per company for now |
| What-if | Multiple drivers | One slider (Fees Charged); other drivers planned |
| What-if | Historical comparison | Scenario vs. actual values not computed yet |
| Register | Export to CSV | Button exists; download not wired |
| Memory | Agents writing | Conversation agent outputs not wired to memory yet |
| Control panel | Email domain allowlist | UI not wired (backend route exists) |

---

## Testing checklist (for the demo morning)

- [ ] Both servers running and responding to health checks
- [ ] `python tools/doctor.py` passes
- [ ] All three seed tools run and complete (check `.sh-tmp/DATA-READY` exists)
- [ ] Five roles can sign in and see their correct top bar links
- [ ] Pulse shows all created walls, charters, baselines, assessments
- [ ] Intent centre shows three rooms lit
- [ ] Wall shows four lanes with cards, invite link works
- [ ] Define shows clusters on shelves, governed rings
- [ ] Build home shows blueprint signed, six months of runs
- [ ] Consume Feeds shows twelve measures, K02 in amber
- [ ] Register shows twelve signed measures
- [ ] Map shows five-column layout, trail is live
- [ ] Control panel shows ardmore company, centre and module switches work
- [ ] No 404s or 500s in browser console
- [ ] All links in the top bar and page headers are live (no 403s for the demo roles)
- [ ] Theme persists on reload (Light, Dark, or Match my device)
- [ ] Copy audit passes: `.venv/Scripts/python -m pytest -q tests/ui_audit/test_copy_rules.py`
- [ ] Link crawler passes: `.venv/Scripts/python .sh-tmp/x3-crawl.py` (check report)
- [ ] Role matrix passes: `.venv/Scripts/python -m pytest -q tests/auth/test_role_matrix.py`
- [ ] Shapes pass: `.venv/Scripts/python -m pytest -q tests/contracts/test_shapes_ardmore.py`
- [ ] Backend and UI type checks pass: `python -c "import sh_platform.app"` and `npx tsc --noEmit`
- [ ] Five demo accounts are confirmed in credentials and match the names in `docs/guides/DEMO-SCRIPT-ARDMORE.md`

---

## How to test in 30 minutes (quick demo prep)

1. **Seeds (10 min):** Run the three seed tools in order with `--reset`
2. **Health (5 min):** Run the five role sign-in screenshots and compare with artboards
3. **Flow (10 min):** Walk the demo script once (5 steps: Aaron → Janet → Daniel → Marcus/Katie → Register)
4. **Checks (5 min):** Run the copy audit, link crawler, role matrix
5. **Go:** Restart servers, open five windows, demo live

---

