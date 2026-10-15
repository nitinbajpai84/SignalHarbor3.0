# Market scan: personalised "what needs me today" feeds (6 Oct 2026)

Ten-minute scan of vendor pages and docs. Items marked (unverified) were not confirmed. No product found covering intent, governed definitions, pipelines and feeds together.

| Product | Home page shows | Covers | Agent drafts? | Weakness | Source |
|---|---|---|---|---|---|
| Atlan | Catalogue, context, certification, approvals | Definitions, governance | Yes (Context Agents) | Catalogue-first, no intent layer, no personal today view (unverified) | https://atlan.com/gartner-magic-quadrant-data-governance-2026/ |
| Collibra | Steward workflow tasks; Maestro Assistant | Governance | Yes (Maestro) | Steward-centric, heavy to configure | https://www.collibra.com/blog/introducing-collibra-maestro-automate-governance-operations-turning-days-of-manual-work-into |
| Monte Carlo | Incidents and alerts | Run | Yes (troubleshooting agent) | Alerts not tasks; engineers only | https://montecarlo.ai/tsa-for-agent-observability |
| Bigeye | Agent Trust Hub | Run, AI governance | Partial | Pivoting to AI trust | https://www.bigeye.com/blog/introducing-agent-trust-hub |
| Viva Goals | OKR tree | Intent | No | Retired 31 Dec 2025, flat adoption | https://learn.microsoft.com/en-us/viva/goals/goals-retirement-faq |
| WorkBoardAI | OKRs; agent inside Microsoft Copilot | Intent | Yes | No link to data | https://www.workboard.com/blog/best-viva-goals-alternative.php |
| Tableau Pulse | Personal metric digests by Slack and email | Consume | Partial | Weekly digests; one off-cycle alert a day | https://help.tableau.com/current/online/en-us/pulse_explore_metrics.htm |
| ThoughtSpot | Watchlists, Spotter agents | Consume, some build | Yes | Analytics only | https://docs.thoughtspot.com/cloud/26.5.0.cl/spotter-agents |
| Power BI Copilot | Copilot on the home page | Consume | Answers, not a feed | Needs capacity and admin enablement | https://learn.microsoft.com/en-ie/power-bi/create-reports/copilot-chat-with-data-standalone |
| Metabase | Subscriptions and alerts; Metabot in Slack | Consume | Creates alerts | Push is user-configured | https://www.metabase.com/docs/latest/ai/metabot-slack |
| Slack / Teams | AI Recaps daily digest; meeting recaps | Delivery channel | Summaries | Only as good as what is in chat | https://slack.com/intl/en-au/blog/news/work-faster-and-smarter-with-slack-ai |
| Jira / Asana | My work; Inbox filtered to what matters; agents take work | Tasks | Yes (Rovo, AI Teammates) | No data semantics | https://www.atlassian.com/software/jira/ai |
| Databricks Genie | Agent mode plans and runs queries | Consume | Yes | Pull-only (unverified) | https://docs.databricks.com/aws/en/genie-agents/agent-mode |
| Snowflake Intelligence | Conversational agents over data | Consume | Yes | Tied to Snowflake | https://itdaily.com/news/cloud/snowflake-intelligence |
| dbt agents | Developer, Discovery, Observability, Analyst agents | Build | Yes | Developer-facing | https://www.getdbt.com/blog/building-the-agentic-data-stack-a-practical-dbt-guide-for-the-ai-era |
| Wren AI | Semantic layer with text-to-SQL via MCP | Definitions, consume | Yes | Semantic layer only | https://getwren.ai/post/why-the-semantic-layer-is-essential-for-reliable-text-to-sql-and-how-wren-ai-brings-it-to-life |
| Productboard Spark | Product agent: briefs, PRDs | Intent (product) | Yes | Not data | https://www.productboard.com/blog/introducing-spark-ai-product-management-agent/ |
| Miro / Mural | AI clustering and briefs on the canvas | Intent | Yes | Stops at the brief | https://miro.com/ai |

## Answers
- No single product covers intent to governed definitions to pipelines to feeds for a mid-size company. Atlan's context layer is the nearest; it has no intent-to-feed loop.
- What brings people back: a filtered inbox with the action one click away; push into email, Slack, Teams; work that can be handed to an agent; the counter-case is Viva Goals, a destination app retired for flat adoption. No hard retention numbers found.
- Missing in the market: a role-aware "needs me today" queue linking intent to definition to pipeline to feed; agents drafting every artefact with humans approving; a data product manager role for the business side.
- Why feed pages fail: notification fatigue (override rates near 90% in clinical systems, about 3% of ops alerts acted on; secondary sources), empty or stale feeds, lost trust after one wrong number, destination-app syndrome.
