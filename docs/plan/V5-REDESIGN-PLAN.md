# V5 redesign plan (Nitin, 11 Oct 2026)

One sentence per centre:
- **Action:** what you must act on today. The landing page after sign-in.
- **Build:** everything new, as one guided path from idea to delivery.
- **Consume:** what you read every day: the Morning Note, reports, market signals.
- **Map:** one connected company map.

## 1. Action (first, the daily pulse)
- Landing page after sign-in for every role. Today (needs me, worth a look), cases, reconciliations, manager follow-ups, approvals waiting for me (studio dashboards, plans, intents), tickets.
- Nothing to read-only; reading lives in Consume.

## 2. Build (one guided project path)
**Build landing = ongoing projects**: a card per project with its stage on the five-step path, owner, last activity, what is waiting and for whom; filters (mine, waiting for me, live). One button: **New project**.

**A project is a stepper with five steps, one page each, always visible as a progress rail with a one-line explanation of each step:**
1. **Intent** (North): what is this project about, who reads it, what they decide, how it is done today. The conversation and the intent of work beside it (today's Intent centre moves here).
2. **Architecture alignment** (Span): the layers, the tables this project needs, gold tables proposed; the head of data approves.
3. **Pipelines**: sources to gold, Try it on a copy, schedule, go live.
4. **Dashboard studio** (Lumen): widgets, approval, publish.
5. **Delivery**: how people receive it. Consume (published dashboard), the Morning Note section, scheduled messages to Slack / Teams / email (a widget or a summary, daily or on change), alerts on thresholds; each delivery approved like a dashboard.

The Intent centre disappears from the top bar; its pages become step 1. Old links redirect. Nothing is dropped (FEATURE-REGRESSION-AUDIT).

## 3. Consume (one clean reading room)
Order on the page:
1. **Morning Note** (today, 07:00): NAV and change since yesterday, top movers, issued against known now, performance against benchmark, liquidity and calls due, market drivers, and "needs you today" (links to Action). Every figure has its trail.
2. **Daily P&L and NAV** view.
3. **Market signals**: third-party data and news (index and FX moves, rates, manager news from feeds), clearly marked as outside material.
4. **Reports library**: monthly investment report, family-council pack, manager scorecard, liquidity ladder, exposure and limits; signed, versioned, exportable.
5. **Published dashboards** (by department and project), Shared with you.
- Lumen is one side panel ("Ask about what you see"), not a separate talk box block. "Your projects" leaves Consume (it is Build).

## 4. Map (one connected company map)
- One interactive node graph: people, intents and projects, sources, tables (bronze, silver, gold), dashboards and reports, rules and definitions, cases, agents, conversations; edges labelled (feeds, owns, decided in, defined by, raised from).
- Lenses on the same graph instead of separate tabs: data flow, process, definitions, conversations, health (source freshness and failures shown as node colour).
- Search focuses a node and its neighbourhood; clicking a node opens its card (what it is, who owns it, where it came from, what depends on it).
- Plain states only: "Talking" becomes "Being defined with North"; duplicate test intents removed from demo data.

## 5. Fast, cheap agents
- Fixed replies for greetings, thanks, help (no model).
- An intent classifier (rules, then Jev) picks: fixed reply, cached answer, deterministic figure answer, fast tier, strong tier.
- Answer cache keyed by normalised question + data version + access.
- Streaming replies; prompt caching on fixed instructions. Targets: first words under 1 s, figure answers under 3 s.

## 6. Delivery and connectors (wave 2)
- Slack, Teams, email and webhook channels (delivery step and alerts; approve in Slack).
- Connector framework plus mailbox, SFTP, SharePoint/Drive.
- Pain-point demo mode: a configurable list of a prospect's pain points mapped to what Signal Harbor does, the use case that shows it, and an honest "covered by your PDM" where true (client lists stay in local/).

## Waves
- **Wave 1:** Action landing; Build landing and five-step project path (Intent into Build); Consume reading room with the Morning Note and market signals; Map as one node graph; fast-chat layer.
- **Wave 2:** Delivery channels (Slack, Teams, email, webhooks); connectors; pain-point demo mode; attribution analytics.
- Each card through Jev; offline tests only (no model spend); one small, capped live check when Nitin asks.
