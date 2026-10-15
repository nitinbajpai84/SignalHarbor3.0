# Neera Family Office: manual test of the return cycle

## Neera at a glance

- Neera Family Office (company id `neera`) is a second, synthetic company on the same machine as Ardmore: family office pack, every module switched on, Singapore clock, SGD.
- Set it up, or bring it back, with `python tools/seed_neera.py`. Running it again changes nothing; what it wrote is in `data/neera/settings/seed_neera.json`.
- Ten people, each with a sign-in (`first.last.neera@example.test`; passwords in `data/_control/seed_credentials.txt`, never shared):
  Priya Nair, Principal, sponsor, company-wide. Arjun Mehta, Head of Operations, company admin. Leela Raman, Head of Data, analyst.
  Dev Sharma, Analyst. Kiran Iyer, Operations Lead, owner of the files. Meera Pillai, Compliance Lead, approver.
  Rohan Das, Treasury. Anita Bose, Investments. Sameer Khan, Reporting. Nisha Rao, Technology.
- Six areas: Treasury, Operations, Investments, Compliance, Reporting, Technology.
- The data: 27 measure tables and 43 source tables in the warehouse, 1,035 pipeline runs, 6 alerts, one landing file, 48 office documents on North's shelf.
- Seven sources on the map before anything is defined: custodian daily files, administrator statements, bank balances, FX rates, valuations, the report pack, the family portal.
- Nothing has been started: no intents, no opportunities, no hypotheses, no proving. Intent home (`/centre/intent`) shows the welcome and the Start button.
- The radar (`/centre/intent/backlog`) runs its first scan the first time someone opens it. On a test copy it found 9 cards across the four business views, set 6 aside and hid 7 below the confidence bar.
- Consume (`/centre/consume`) shows the four business views with counts from the first sign-in; the map is at `/centre/intent/graph`.
- Rohan, Anita, Sameer, Nisha and Dev are participants: they do not see the business views or the radar's full cards.
- The office documents come from the shared demo story and still name some Ardmore people; treat them as the office's history.

---

## Before you start

- Address: your test copy at `http://localhost:8300`. If a Neera sign-in is refused there, that copy started before Neera existed; ask for one refresh of 8300, or use `http://localhost:8200` for this walk.
- Sign-ins: `first.last.neera@example.test` (for example `arjun.mehta.neera@example.test`). Passwords are in `data/_control/seed_credentials.txt`.
- Use one private browser window per person, so two people can be signed in at once. A sign-in holds one session: signing the same person in elsewhere signs the first window out.
- Phone steps: open the browser's developer tools, switch on the device toolbar and set the width to 390.
- The walk changes Neera's records. To start again from empty, ask the orchestrator to clear Neera's intents; `tools/seed_neera.py` alone does not remove them.
- Each step gives: the address, who signs in, what the agents did before you arrived, what you do (numbered), what you should see, and the value in one line.
- When something does not match, note the step number, the person, the width and what you saw. That is all a fixer needs.

### The data story you are testing against

Neera's thirteen months of figures, daily files and 48 documents carry eight planted patterns. You do not need the details; you need to know what a good radar does with them.

1. Cash sits idle above the treasury policy in two entities while interest earned stays low. (New revenue)
2. The monthly meeting pack takes far too many hours, and the hours trace to one administrator whose statements arrive late every month. (Process cost)
3. The family opens its reports less and asks the office more questions, mostly about finding their own holdings. (Retention)
4. Private fund valuations from one administrator are two quarters old, and concentration in one issuer drifts up. (Risk)
5. Custody fees at the second custodian stepped up after assets moved to the first custodian and the second fell below a fee tier. Nobody has acted on it. (Process cost)
6. US dollar exposure grew unhedged and lost money when the Singapore dollar strengthened. A decision on hedging is pending. (Risk)
7. Several people want one view of every commitment and capital call, said in different words on walls, check-ins and a brainstorm. (A wish, no measure)
8. A note claims the pack takes longer in volatile months. It does not hold: the link breaks in a later month, and the effort log puts the hours on the late statements. (A false lead the radar must set aside)

Neera differs from Ardmore in one way that matters: no walls, check-ins or brainstorms were loaded. So pattern 7 has no voices yet and cannot appear on the first scan, and patterns 1 to 4 show as data only, with no Initiative behind them. This walk uses pattern 5 for the Initiative, pattern 2 for the Problem, pattern 6 for the Decision and pattern 3 for the Brainstorm.

### Who plays which part

| Person | Sign-in role | Part in this walk |
|---|---|---|
| Arjun Mehta | company admin | Organiser of the Initiative, the Decision and the Brainstorm; head of department in Build |
| Priya Nair | sponsor | Signs the charter, the baseline, the build plan and the release; decides the Decision |
| Leela Raman | analyst | Data owner in Define; architect in Build; signs the build plan as head of data |
| Kiran Iyer | owner | Owns the files and the Operations processes; ops in Build; runs the weekly check-in |
| Meera Pillai | approver | Governance lead in Define; adviser on the Decision |
| Rohan Das | participant | Puts cards on the wall (one sealed); reports in the check-in; reporter of the Problem |
| Nisha Rao | participant | Reports in the check-in |
| Dev Sharma | participant | Data engineer in Build |
| Sameer Khan | participant | Tester in Build; brainstorm participant |
| Anita Bose | participant | Brainstorm participant |

---

## Part 1. Notice

### Step 1. Arjun signs in; Pulse and home are empty

- Address: `/`, then `/centre/pulse`, then `/centre/intent`.
- Who: Arjun.
- Before you arrived: nothing. No intent, opportunity or message exists, so Nira has nothing to put on his day.
- Do:
  1. Open the address, type Arjun's email and password, press the sign-in button.
  2. Read Pulse.
  3. In the top bar, open the Intent Centre.
- You should see: Pulse greets Arjun by first name and says nothing needs him today, with no invented items. The Intent Centre shows "Start your first intent", North's starter suggestions with "Start this" and "Not for us", "The five kinds of intent", and the "Start an intent" button. No counters with made-up numbers.
- Value: a new company opens to an honest empty page with a starting list, not a blank screen or someone else's data.

### Step 2. The radar after its first scan

- Address: `/centre/intent?view=radar&tab=lenses` (or the link "Open the radar" on the home).
- Who: Arjun.
- Before you arrived: the first time anyone opens the radar, the operations monitor reads the measure tables and run log, Lens reads the 48 documents, and North writes a hypothesis for each pattern and checks it against the data before anyone sees it. On a copy this produced 22 records in a few seconds.
- Do:
  1. Open the address. Wait for "Reading the radar." to finish.
  2. Read the four columns: New revenue, Process cost, Retention, Risk.
  3. Read the line about hidden opportunities.
  4. Read the aside "Checked and set aside", then "How the radar works".
  5. Switch to the tab "By area", pick Operations, then Treasury.
- You should see: about nine cards (on the copy: New revenue 2, Process cost 3, Retention 2, Risk 2). They cover idle cash above policy and interest on cash, meeting-pack hours, custody fees, hedging cost, family report opens and report questions, stale valuations, and unhedged FX loss. Each card shows a belief in one sentence, the measure, a baseline, "Not available yet" with the reason for anything missing, confidence in words and an evidence mix. The hidden line reads "7 opportunities are hidden because North is less sure than the company setting allows." "Checked and set aside" lists about six items, one of them the pack hours moving with market volatility, each with its reason and the record that broke it. There is no card about one view of commitments and calls (no voices yet). The live scan may differ by a card or two from the copy because North judges live.
- Value: patterns nobody asked about reach the right person already checked, and the false lead is set aside with its reason.

### Step 3. Read one opportunity and pick it up into an Initiative

- Address: the card "K22 moved up" (custody fees) opens `/centre/intent/backlog?opportunity=<id>`.
- Who: Kiran first, then Arjun.
- Before you arrived: North wrote the hypothesis (belief, measure, baseline, lens, confidence), ran the counter-evidence check ("Holds") and drafted the six Initiative start answers, each marked "Guessed by North". It did not set a target or a review date: those are a person's call. "Pick it up" stays disabled until a review date exists.
- Do (Kiran, in his own window):
  1. Sign in as Kiran. Open `/centre/intent?view=radar&tab=areas` and pick Operations.
  2. Open the custody fees card.
  3. Read "Hypothesis", "Evidence by kind" (Data, Documents, Voices), "Counter-evidence check", "North's judgement" and "Proposed start answers".
  4. In Target, type a target value and pick a date; press "Save target".
  5. In Review date, pick a date about three months ahead; press "Save review date".
- Do (Arjun):
  6. Open the same card.
  7. Press "Pick it up".
  8. The Initiative start opens with the answers filled. On each question read the draft, press "Use this draft" or change it, then "That is right" and "Next":
     - Goal: keep the drafted goal about custody fees.
     - People: add Kiran Iyer and Rohan Das to take part; Priya Nair as sponsor.
     - Build: "Yes".
     - Definitions: "Some of them".
     - Areas: Operations and Treasury.
     - Deadline: keep the drafted date.
  9. On Review press "That is right, open this intent".
- You should see: after each save, "Saved as a new version." The evidence lines link to the fee records and the custodian documents; a document Kiran may not open reads "A document you cannot open". After "Pick it up" the opportunity reads "Picked up" with "Became an Initiative". The new Initiative's page shows the stage "Think unfiltered" and the stage clock.
- Value: the opportunity, its evidence and its hypothesis become the Initiative's starting point in under ten clicks; nobody retypes the case.

---

## Part 2. Think and Define

### Step 4. The wall with three people, one sealed card

- Address: `/centre/intent/<id>`, then `/centre/intent/<id>/wall`.
- Who: Arjun, Kiran, Rohan.
- Before you arrived: North prepared the wall and drafted the invitations; Nira put an invitation on Kiran's and Rohan's day. North draws its suggestion cards from the pack and the documents.
- Do (Arjun):
  1. On the Initiative page press "Open the wall".
  2. On the wall's stage bar press "Start the briefing", then "Yes" at "Are you sure?".
  3. Press "Open the private rooms", then "Yes".
- Do (Kiran, then Rohan, each in their own window):
  4. Sign in. Under "Your turn" on Pulse or the Intent home, open the invitation and press "Accept".
  5. Open the wall. In your private room press "Talk to North".
  6. Answer North's questions one at a time (what it is in business words; where it bites; how it is tracked today; the most technical definition, where "I do not know" is fine). Use North's draft or type your own; press "Answer" after each.
  7. After two answers, press "Put it on the wall now".
  8. Rohan only: add a second card about a colleague's workload and tick "About people, pay or personal data (seal it)" before putting it on the wall.
  9. Optional: press "Pick it up to make it yours" on one of North's dashed suggestion cards.
- Do (Arjun):
  10. Add one card of your own the same way.
- You should see: while the rooms are open Arjun sees "n cards are in from the private rooms", not their words. Four lanes: TRACKING NOW, MISSING, WATCH, LEVERS. Seats taken match the people who joined. Rohan's sealed card reaches Arjun and Kiran as "A sealed card about ..." with no text; Rohan sees his own words. "Put it on the wall now" stays disabled until two of the four questions are answered.
- Value: each person says what they know privately and quickly, and sensitive points are counted without being exposed.

### Step 5. Close the wall

- Address: `/centre/intent/<id>/wall`.
- Who: Arjun.
- Before you arrived: nothing new; the cards wait in the rooms.
- Do:
  1. Press "Close the rooms and bring everyone to the wall", then "Yes".
  2. Read the wall: counts per lane and who contributed.
  3. Press "Close the wall", then "Yes".
- You should see: the cards appear by lane; untouched suggestion cards are dropped and not counted; Define opens. North names and colours the clusters; the frozen wall is read only and offered as charter page one.
- Value: the wall freezes into a dated record and the clustering is done for the committee, not by it.

### Step 6. Define: clusters, process map, data sources

- Address: `/centre/intent/<id>/define` (tab "Clusters and shelves"), then `?tab=process-map`, then `?tab=data-sources`.
- Who: Arjun (clusters), Leela and Kiran (process map), Kiran (sources).
- Before you arrived: North clustered the cards and proposed a shelf for each. Lens drafted the processes each cluster touches and the sources behind them from the cards, documents and the systems list, each cell marked guessed with its source. Nira put "Confirm your source" on Kiran's day.
- Do (Arjun):
  1. On "Clusters and shelves", move each cluster to Must, Should, Good to have or Future (drag, or "Move to" at 390).
  2. Try moving a cluster whose measures are not governed yet to Must.
  3. For Future, give a reason and a review date.
- Do (Leela, then Kiran):
  4. Open "Process map". Read Lens's drafted process and edit one step. Kiran presses "Confirm this process" on the one he owns; a process that is not yours gets "Not mine, it is..." and the owner's name.
  5. Kiran opens "Data sources" and presses "Confirm this is how <source> works" on each source he owns, then "Done with data sources".
- You should see: the move of an ungoverned cluster to Must is refused with a message naming the missing fields and who must confirm each. Edited cells change from "Guessed" to "Edited". The data sources header counts "n named, n confirmed by their source owner".
- Value: the committee sorts and confirms drafts instead of writing process maps and source lists from scratch.

### Step 7. Define: glossary, catalogue, governed state, Lens questions, source map

- Address: `/centre/intent/<id>/define?tab=glossary`, `?tab=catalogue`, `?tab=source-map`.
- Who: Meera (terms and classification), Leela (catalogue), Kiran (owner fields and Lens questions), Arjun (source map and close).
- Before you arrived: Lens drafted every business term with a source line and flagged terms with more than one meaning. It drafted each measure's technical definition, catalogue entry and six governed fields (owners, classification, who may see, resolving team and week, what it affects, review date), and asked each named owner at most three questions.
- Do (Meera):
  1. Open "Glossary". Under "Ambiguous terms" open one term, read the meanings found and press "Pick one meaning" (or "Accept as a known risk" with a reason).
  2. Press "Confirm my terms" for the terms you own.
- Do (Leela):
  3. Open "Catalogue". Open each Must and Should measure and press "Confirm data owner".
- Do (Kiran):
  4. On the Lens strip at the top of Define, answer each question ("Use this meaning", "Not mine", or "Say it in your words" then "Save my answer").
  5. In the catalogue's governed state press "Confirm owners" on the measures he owns.
- Do (Meera):
  6. In the governed state press "Confirm classification" and "Confirm who may see".
- Do (Arjun):
  7. Open "Source map". Press "Confirm as strategic" (or "Confirm as not strategic" with a reason) on each source.
  8. Back on "Clusters and shelves", move the now governed clusters to Must or Should.
  9. Press "Close the session and write the charter draft" and confirm.
- You should see: a cluster's dashed ring turns solid once all six fields are confirmed. Lens never overwrites a wording a person typed; a later draft shows as a proposal. Kiran sees "Lens is asking because you are named as the owner." No person gets more than three questions.
- Value: definitions, ownership and governance are confirmed by the right named people in minutes each, with every line traced to where it came from.

---

## Part 3. Decide

### Step 8. The charter, with the success measure from the hypothesis; Priya signs

- Address: `/centre/intent/<id>/charter`.
- Who: Arjun drafts; Priya signs.
- Before you arrived: North drafted the whole charter when Define closed: the frozen wall as page one, problems with priority, "so that" lines, measures, glossary and catalogue summaries, "Build needed: Yes" with the reason, and the success measure carried from the opportunity's hypothesis (measure, baseline, and the target and review date Kiran set).
- Do (Arjun):
  1. Read each page. On each North "so that" draft press "Use this line" or "Edit".
  2. Check the success measure; change the target or review date if needed and press "Save target and review date".
  3. Press "Send up for signing".
- Do (Priya):
  4. Sign in. Open the line on her day, or the address.
  5. Press "Sign the charter", then "Yes, I am the sponsor. Sign".
- You should see: Arjun cannot sign. "Sign the charter" stays disabled while a draft line is unchecked. The success measure shows the same measure and baseline as the radar card. After signing: Priya's name, role and date; the charter is read only; "Download PDF" works.
- Value: what was noticed is what gets signed; the charter's success measure is the hypothesis, not a fresh guess.

### Step 9. Who does what

- Address: `/centre/intent/<id>/charter?focus=roles`.
- Who: Arjun names; each person accepts.
- Before you arrived: North drafted the roles from the people on the wall and in the catalogue, marked guessed.
- Do (Arjun):
  1. Set Architect: Leela Raman; Head of department: Arjun Mehta; Developer: Dev Sharma; Tester: Sameer Khan; Sponsor: Priya Nair; Operations: Kiran Iyer; Kept informed: Rohan Das.
- Do (Leela, Dev, Sameer, Kiran):
  2. Each signs in, opens the role line on their day and presses "Accept".
- You should see: only named people, no blank rows; each edit saves at once; a decline returns to Arjun's day with the reason.
- Value: the build team is named and has agreed before Build starts, so no hand-over lands on someone who did not know.

### Step 10. Build-ready check

- Address: `/centre/intent/<id>/build-ready`.
- Who: Arjun.
- Before you arrived: North recomputes the seven lines on every write and drafts a to-do for each failing line, naming the person.
- Do:
  1. Read the chip "Build-ready: n of 7". Press "Show what is missing".
  2. On each failing line press "Fix it" (it opens the record) or "Nudge" (North drafts a reminder to the named person).
  3. Press "Recheck now" after the fixes.
- You should see: seven lines: charter signed; business definitions; technical definition, catalogue and governed state; process owners; source owners; who does what; build needed. "Hand to Build" stays disabled until 7 of 7.
- Value: readiness is checked against the records, not asserted in a meeting.

### Step 11. Hand to Build

- Address: `/centre/intent/<id>/build-ready`, then `/centre/build/gap-analysis?from=<id>`.
- Who: Arjun (only the organiser hands over).
- Before you arrived: nothing new.
- Do:
  1. Press "Hand to Build". Read the dialog (it names the catalogue version and the number of sources) and confirm.
- You should see: "Handed to Build." Build opens at room 0, "Moment of truth", with a banner naming the Initiative, Arjun and the time, the counts of measures and sources, and "What Build received" (charter, catalogue, processes, source map). If it reads "Not available yet: no gap analysis has been started for this hand-over", carry on with step 12.
- Value: Build receives the signed charter, catalogue, processes and source map as records, not as an email.

---

## Part 4. Build

### Step 12. Gap analysis: baseline and build plan

This stretch reuses the earlier Assess and plan module. On a fresh Initiative it has been walked once, by a tester with stand-in records, so expect rough edges; note where it stops.

- Address: the baseline page `/centre/intent/baseline/<baseline id>` (linked from the charter's Baseline line and from Priya's day), then `/modules/m3_connect`.
- Who: Priya, then Leela, then Priya.
- Before you arrived: Lens built the baseline from Define (measures, definitions, owners). Once the baseline is signed, Lens scores the sources, runs the trial against the figures already reported and drafts a phased build plan.
- Do:
  1. Priya opens the baseline page and presses "Sign the baseline". If the gate lists something missing, each line links to where it is done.
  2. Leela opens `/modules/m3_connect` and presses "Start from the signed baseline".
  3. Leela walks the steps "Data request and scan", "Trial and findings" and "Build plan". On each plan item she presses "Accept" (or "Accept all remaining").
  4. Leela presses "Sign as the head of data".
  5. Priya opens the same plan and presses "Sign as the sponsor".
- You should see: the trial counts match, gap and not yet per measure; the plan in bands, marked "Drafted by Lens"; both signatures with names and dates.
- Value: the build plan is drafted from the trial and only signed by people.

### Step 13. The Build chain

- Address: `/centre/build` (panel "The chain"), then `/centre/build/change/<change id>?step=n`.
- Who: Leela (architect), Arjun (head of department), Dev (data engineer), Sameer (tester), Priya (release), Kiran (ops).
- Before you arrived: once the plan was signed, the Architect drafted the change note (why, what changes, decision and alternatives, build steps, what to test, run book additions, risks), each line marked guessed with its source, and placed the new tables in the company architecture record. Nira put "The Architect drafted the change for <title>. Check it." on Leela's day.
- Do:
  1. Leela: open the chain row. Read the seven sections; edit one decision line if you disagree. Press "Send for approval".
  2. Arjun: open step 2. If "Approve the design" is disabled, read North's line (for example "1 component has no owner"). Press "See the diagrams", select the component named, set Owner to Kiran Iyer, press "Save" and go back. Press "Approve the design".
  3. Dev: open step 3. Press "Built, ready to test" once the build steps read done. (Dev is a participant; if the Pipelines page refuses him, Leela runs the pipeline from `/centre/build/pipelines`.)
  4. Sameer: open `/centre/build/prove`. For each measure compare Ours and Reported; press "Sign UAT", or "Send back with a note" with a reason.
  5. Priya: open `/centre/build/prove` and press the release button ("Release n measures").
  6. Kiran: open step 5. Read the run book additions. Press "I run this from today".
- You should see: "The chain" shows five steps (Architect, Approval, Data engineer, Tester, Ops manager) with names and "With <name> for n working days". Only the named person can act at each step ("Only the named person may act at this step."). A send-back returns the change one step and puts the reason on the earlier person's day. After release the architecture record moves to a new version; after step 5 the change is live. Known from Ardmore: a mismatch between the warehouse and the reported figures can flip Prove to a gap; the measure's owner may press "Accept the gap" with a reason.
- Value: every build step has a drafted note and a named person; nothing goes live without the tester's and the sponsor's signatures.

---

## Part 5. Run and consume

### Step 14. Consume by business view, and a context card

- Address: `/centre/consume`, `/centre/consume/lens/process-cost`, then the custody fees measure page under `/centre/consume/feeds/<code>`.
- Who: Kiran.
- Before you arrived: Consume groups the existing measures, briefs, builds and opportunities under four business views and adds no figure of its own. When the design was approved, the Architect drafted the context card for the custody fees table and Lens drafted "What it means"; Nira put "A context card waits for you" on Kiran's day because he owns the table.
- Do:
  1. Open Consume. Read the four tiles (New revenue, Process cost, Retention, Risk) and their counts.
  2. Press "Open Process cost". Switch between "Everything" and "My line of work".
  3. Read "What our data says", "What we are building" and "What we should consider next".
  4. Open the custody fees measure and read the context card.
  5. Press "Correct a line" on "Last change and why", type one sentence, press "Save the line".
  6. Press "Confirm this card".
  7. Type a question in "Ask Lens about this measure" and press "Ask Lens".
- You should see: the Initiative under "What we are building" and the remaining opportunities under "What we should consider next". The card reads Draft, then Confirmed with Kiran's name. Lens's answer cites the confirmed card and the Initiative. If the card reads "No context card yet", the design was not approved (step 13, action 2).
- Value: a reader gets the right number with its meaning, lineage and owner, grouped by the question the office asks.

### Step 15. What-if into an opportunity

- Address: `/centre/consume/what-if`.
- Who: Kiran.
- Before you arrived: nothing; the what-if reads the company map.
- Do:
  1. Pick a driver whose path reaches a measure (for example statement lateness or document intake effort).
  2. Type a change in percent, for example minus 20.
  3. Read "What moves". Press "Keep this scenario".
  4. Press "Turn this into an opportunity". In the sheet, edit "What you believe", pick the business view Process cost and press "Raise it".
- You should see: "Raised. It is on the opportunities list for review." The new opportunity reaches the radar as a person's raise and North judges it like the others. The estimate is labelled a straight line, not a target.
- Value: a hunch from a scenario enters the same checked path as everything else.

### Step 16. A weekly check-in, reported on the phone

- Address: `/centre/intent/new` (tile "Weekly check-in"), then `/centre/intent/<id>/week`, then `/centre/intent/<id>/review`.
- Who: Kiran sets it up and reviews; Rohan and Nisha report at 390 width.
- Before you arrived: nothing for this series. North suggests questions from the pack.
- Do (Kiran):
  1. Press "Start an intent" and pick "Weekly check-in".
  2. "Which ops area is this for?": Operations. "Who reports each week?": Rohan Das and Nisha Rao. "Which day does the week close?": keep Friday. The reviewer is Kiran.
  3. Press "Start the check-in".
- Do (Rohan, at 390 width):
  4. Sign in. On Pulse press "Answer your check-in".
  5. Under "Broke" add one item: "The administrator's statement file came late again; the pack waited two days." Set "How bad was it?" to "Slowed us".
  6. Answer the others or press "Nothing to add here". Press "Send my week".
- Do (Nisha, at 390 width):
  7. The same with one item of her own, ticking "Hide my name on this item" on it.
- Do (Kiran):
  8. Open the review. Press "Close the week" when it is offered, then "Start review session".
  9. On Rohan's broke item choose "Becomes a Problem" and press "Create the Problem draft".
- You should see: each entry takes about two minutes on the phone. Rohan never sees Nisha's named items before the week closes (a privacy fix is in flight; note it if he does). Nisha's hidden item shows as "Anonymous" to Kiran. The week does not read "closed" while its close time is still ahead.
- Value: an area's week is captured in two minutes a person, and a broke item becomes work in one click.

### Step 17. A Problem from the broke item

- Address: `/centre/intent/<problem id>` (from "Open the Problem draft").
- Who: Kiran (owner), Rohan (reporter).
- Before you arrived: North drafted the Problem from Rohan's item (what is wrong, how hard it bites, who feels it), linked the measures and the late-file alerts it found, and proposed an owner.
- Do (Kiran):
  1. Press "Open the Problem draft". Read "Drafted by North from your item. Edit anything." and press "Open this problem".
  2. Press "Accept" as owner (or "Pass it on" with a reason).
  3. Press "Draft the cause", read it and press "Confirm this cause".
  4. Write the fix, press "Save fix", then "Close and send for confirmation".
- Do (Rohan):
  5. Open the line on his day and press "It is fixed for me" (or "Still happening for me").
- You should see: "Recent alerts and range breaks" lists the late administrator files; "Similar past problems" is empty on Neera. The closure goes to Rohan to confirm. A known gap in flight: the reporter cannot add evidence posts yet.
- Value: a weekly complaint becomes an owned, explained, fixed and confirmed record.

### Step 18. A Decision with Meera advising

- Address: `/centre/intent/new?type=decision`, then `/centre/intent/<id>`.
- Who: Arjun opens; Meera and Rohan advise; Priya decides.
- Before you arrived: nothing for this decision. The radar already holds the unhedged FX loss card.
- Do (Arjun):
  1. "What must be decided?": "Do we restart FX forwards on the US dollar balances this quarter?"
  2. "Who decides?": Priya Nair. "Whose advice do you want?": Meera Pillai and Rohan Das. "By when?": a working day next week. Areas: Treasury and Compliance.
  3. Press "Open this decision".
- Do (Meera, then Rohan):
  4. Open the invitation and press "Accept".
  5. Press "Give your view", type a note and press "Add a note". Meera also presses "Add an option" and adds one option.
- Do (Priya):
  6. Read the options and North's draft recommendation with "Rests on:".
  7. Press "Choose" on one option, type the reason under "Why this option?", press "Record my decision" and confirm.
- Do (Arjun):
  8. Press "Close this intent" on North's closure draft.
- You should see: option cards say who added them (a name, "an adviser" when anonymous, or North for a draft), never "undefined". Meera moves from "Not replied yet" to replied after her note. On the next radar scan the FX card links to this Decision.
- Value: a pending decision gets advice on record, a named decider and a reason that outlives the meeting.

### Step 19. A Brainstorm with what next

- Address: the family report opens card on the radar, then `/centre/intent/new?type=brainstorm&from=<opportunity id>`, then `/centre/intent/<id>`.
- Who: Leela sets the review date; Arjun organises; Sameer, Anita, Dev and Leela take part.
- Before you arrived: North's hypothesis on report opens holds; "Think it through first" waits for a review date.
- Do:
  1. Leela opens the card (Retention column), sets a review date and presses "Save review date".
  2. Arjun opens the card and presses "Think it through first".
  3. The Brainstorm start opens filled from the hypothesis. Check each answer ("That is right" or "Let me correct it"). People: Sameer, Anita, Dev, Leela. Session date: the next working day. Press "Looks right", then "Open this brainstorm".
  4. Each participant opens the invitation, presses "Accept" and adds one or two ideas with "Add your idea". (To test pattern 7, two of them write the wish for one view of all commitments and calls in their own words.)
  5. Arjun opens the session early with "Open the session", then presses "Move to group", then "Move to converge".
  6. Arjun presses "Open the count"; each participant presses "Back this" on the ideas they favour; Arjun presses "Close the count".
  7. Arjun presses "Draft it" on the top idea, edits it and presses "Confirm this outcome".
  8. Under "What next" press "Turn into an Initiative" (or close the brainstorm and use "Start the Initiative" on the closure).
- You should see: other people's ideas stay private until the session opens; anonymous ideas are counted, never named; the outcome carries the same hypothesis; the follow-on Initiative start opens filled from the chosen idea.
- Value: an opportunity can be thought through with the people who know it before anyone commits to an Initiative.

---

## Part 6. Prove

### Step 20. Proving

- Address: the Initiative's page `/centre/intent/<id>` (the Proving panel sits under the stage view).
- Who: Arjun and Priya.
- Before you arrived: when Priya signed the release in step 13, Proving started from the go-live date with the hypothesis frozen at the charter signature. North drafts a weekly uplift report on the first Friday after the start.
- What to expect on Neera: a fresh Initiative needs new periods of data to land before a verdict means anything. Neera's figures are a fixed history, so the panel will read "Proving" with "No reports yet." or "No new period landed, nothing to confirm". That is correct, not a fault. The seeding command `python -m sh_platform.intents.proving seed ./data neera` only starts Proving for Initiatives seeded with a hypothesis; Neera has none, so it does nothing here.
- To see the Proving screens with real before and after, use Ardmore on 8300:
  1. Sign in as Janet (`company_admin.ardmore@example.test`).
  2. Open `/centre/intent/ini-37c78119f8a10a2611a942f7fdb17551` ("Sweep idle cash above the policy floor into money market funds").
  3. Read "What we believed", "Before", "Target", "Since the start", "Latest report" and "North's verdict".
  4. Press "Confirm this report", or "Change the verdict" with a reason; then "Open the review".
  5. Repeat as Daniel (`sponsor.ardmore@example.test`) for the review.
- You should see on Ardmore: the cash sweep reads working; the confirm and review buttons respond (one tester reported them dead; note it if they are).
- Value: the office learns whether the change moved the measure it was meant to move, and a failed bet goes back to the radar with its lesson.

---

## Inputs per journey (from the input ledger)

From `docs/product/input_ledger.yaml` via `tools/ledger_summary.py` (1,527 rows on 7 October). These are counts of inputs, not clicks. The ledger's minutes are planning estimates, not measurements, so none are quoted.

| Journey | Typed by a person (manual) | Confirmed by a person (confirm) | Derived or automatic | All |
|---|---|---|---|---|
| Initiative (notice to hand-off) | 138 | 96 | 187 | 421 |
| Build chain | 15 | 3 | 22 | 40 |
| Consume and what-if | 16 | 3 | 30 | 49 |
| Weekly check-in | 42 | 15 | 76 | 133 |
| Problem | 45 | 15 | 43 | 103 |
| Decision | 24 | 13 | 30 | 67 |
| Brainstorm | 65 | 22 | 57 | 144 |
| Shared across journeys (record, people, clock, Pulse, radar, Proving) | 146 | 56 | 279 | 481 |
| Admin | 17 | 4 | 68 | 89 |
| All | 508 | 227 | 792 | 1,527 |

By stage of the cycle, Notice has 65 typed, 30 confirmed and 142 derived or automatic; Prove has 49, 15 and 125. The ledger still marks 92 rows for the radar, Proving and the Build chain as "missing in build" although those features are now built; they are counted under the mode their spec gives.

## Where each step is specified

- Step 1: specs 04 (home), 13 and 45 (Pulse and what waits), 18 (empty states).
- Steps 2 and 3: specs 56 (data-backed opportunities), 57 (radar and hypothesis), 22 (Initiative start).
- Steps 4 and 5: specs 23 (wall), 24 (cards), 25 (suggestion cards); journey 50, steps 3 to 5.
- Steps 6 and 7: specs 26 (Define), 27 (process map), 28 (data sources and source map), 29 (glossary), 30 (catalogue), 31 (governed state), 44 (Lens in Define).
- Steps 8 to 11: specs 32 (charter), 34 (who does what), 33 (build-ready and hand-off), 57 (success measure); journey 50, steps 10 to 13.
- Steps 12 and 13: spec 59 (Build chain and architecture); `docs/specs/BUILD-CENTRE-SPEC.md` for the earlier Build rooms and Assess and plan.
- Steps 14 and 15: spec 60 (Consume by business view, context cards, what-if).
- Step 16: specs 38 to 40; journey 52.
- Step 17: specs 41 and 42; journey 53.
- Step 18: spec 43; journey 54.
- Step 19: specs 35 to 37 and 57 (think it through first); journey 51.
- Step 20: spec 58 (Proving and the weekly uplift report).
