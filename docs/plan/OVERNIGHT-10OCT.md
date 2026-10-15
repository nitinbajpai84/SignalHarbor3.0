# Overnight 10 Oct 2026: what Nitin asked before sleeping (02:15)

1. **Fix all open problems and test all ten use cases thoroughly** (answer key, checkers, journeys, use-case analysts, live agents). Nothing goes back to Nitin until it is thorough.
2. **Build centre = three rooms, and make it engaging ("funky")**: **Pipelines** (sources → bronze → silver → gold, runs, schedule, Airflow export), **Dashboard studio** (canvas with slots, widgets, Lumen fills slots, submit → approve → publish to Consume; docs/plan/DASHBOARD-STUDIO.md), **Architecture** (the system and data model: layers, tables, relationships, lineage diagram, Span explains). Build is where people build.
3. **Consume landing: what a family office wants to see every day, at the top**: NAV (total and by entity, USD/SGD, issued vs known now), performance (month and year to date, portfolio vs benchmark), the key levers that moved it (largest contributors, revisions, timing, FX), market drivers (index and FX moves from market data), liquidity headline. Below: project-specific and department-specific reporting (published dashboards), Shared with you, company reports, outside data and insights.
4. **NAV consolidation issues stay in Action** (cases, reconciliations).
5. **Comments with history**: people can comment on performance reporting (dashboards, widgets, Office view lines, the CIO Brief, a figure), comments are kept as history (append-only, edited and deleted shown as such), mentions notify the person, and a comment can **trigger an action**: "Raise as a case" creates an Action case or ticket linked back to the comment.
6. Running before sleep and to finish: agent quality campaign (live model, up to 3 cycles), Dashboard studio (DS1), demo guide, new-use-case walkthrough, sponsor video (then a second pass covering every feature, 3-5 min, after the agents are final), website (refresh screenshots at the end).

## Morning deliverables
- A fresh server with everything and fresh data (port 8502), keeping 8501 as Nitin left it.
- docs/test/OVERNIGHT-REPORT-10OCT.md: what was built, what was tested with pass rates (ten use cases, agents scorecard), what is still open, how to see each thing.

## Product findings from the demo guide (to fix overnight, non-agent)
- Build rooms (Design, Scan, Mapping sheet, Pipeline, Run log) are empty for the seeded live project: the seed must write the plan, mappings, scan and run log the rooms read (seed_10uc / seed_v3_demo).
- Settings says "Testing uses made-up answers only" but Testing calls the free-tier model: fix the wording; the switch is company-wide: say so beside it.
- Dates follow the browser time zone; "Signed" shows the seed day not 3 Oct: use the company time zone and seeded dates.
- Settings > Signed register says nothing is signed although the intent and four measures are signed.
- Dashboard charts are narrow with no value labels.
- The SOP downloads as .md on the Intent page but .docx on the project page: one format (.docx) everywhere.
- Answer key: Raj sees 9 cases; Sofia has no Consume tab (decide: give participants Consume read? Nitin said Consume is for everyone to read: yes, give every role Consume).
- Demo valid 9-14 Oct only: pin the demo "today" to 9 Oct via a company setting so the story holds on any day.
- Open after PF1/PF2: lineage test test_c1_a10_7_and_a10_8_tiles_trace_to_bronze (b6_plan builds lineage from depends_on only; gold should trace through silver to bronze via the catalogue, not depends_on); seed signs the intent with the run time instead of 3 Oct 2026.

## Decisions taken overnight (orchestrator, for Nitin to confirm)
- Dashboards started in Consume become personal drafts; sharing to others goes through the Build studio approval (Nitin: build in Build, approved, published to Consume). Applied in CL1.
- Approvers: any head of data (architect seat) or sponsor role except the maker; narrowing to the project's named people is left open.
- Open after BC1: Pipelines Silver card should list the silver tables this project's gold tables read (get_lineage), not the first core tables; b6diagram has two empty white bars, a white background in dark mode and a cut-off right column; at 390px the top bar wraps the brand and cuts the company badge.

## BLOCKER for Nitin (found ~04:30): model accounts out of credit
- Google prepaid credits depleted (HTTP 402); OpenRouter key has about 0.44 of its 20 USD limit, below what one fallback call reserves (4,096 tokens). Every agent now answers rules-only; confirmed on the lab server (Lumen rules_only: true).
- Only Nitin can top up (payment). Until then: no live agent verification; the agent campaign is stopped after its cycle-1 fixes; non-model fixes continue.
- Product gap found: when the provider refuses for billing, users see only "I could not reach the model"; admins should see "The model account is out of credit (Google / OpenRouter); ask the administrator to top it up" in Settings and on the agent reply for company_admin.
