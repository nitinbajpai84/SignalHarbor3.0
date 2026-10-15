# Signal Harbor: the final architecture in one page

Diagram: `sh-final-architecture.html` (source `sh-final-architecture.json`, drawn with Archify; edit the JSON and re-render, never the HTML).

## What it is
One web application that a company's people use in a browser. Everything runs as one Railway service; each company's data lives in its own plane on a persistent volume.

## The parts, left to right
- **People.** Sponsor/CIO signs the charter in Intent. Participant/risk explains cases on Action. The analyst builds in Build and works cases. Approver/finance approves dashboards and cases. Head of data owns the Map and approves plans. The admin runs people and Settings (company admin) or the control plane (super admin).
- **Browser UI.** Four centres: Intent (talk to North), Action (Today and cases, Tally), Build (Architecture, Pipelines, Dashboard studio), Consume (published dashboards and offers). Plus Map (tables and lineage) and Settings.
- **API (FastAPI).** Every route is listed in one permission table; a route not listed is refused (default deny). The control plane decides which modules a company has.
- **Four agents.** North (intent), Tally (data analyst), Span (design and pipelines), Lumen (dashboards and briefs). All run on one shared read-only loop with tools that return counts and totals, a guard (every figure must trace to a recorded fact; outside text is data, never an instruction), memory (short term, long term, shared) and a context map with local search over documents.
- **One exit.** The model router picks the tier (fast, specialist, manager) within the company mode (Testing or Real) and falls back to another model when a provider is out. The egress gateway is the only way out: allowlist, name vault masking, raw-row block, log, and an outage breaker. It reaches OpenRouter models and Google speech.
- **Company data plane.** Landing keeps originals; Bronze loads as is; Silver is the core model; Gold is per project. Beside them: documents and passages, the graph, cases and comments, logs and traces.
- **Pipelines and checks.** A plan is tried in a sandbox, goes live only after approval, can run on a schedule, and can be exported as an Airflow DAG. Checks (cash, NAV, limits, trades) read the Silver core tables and open cases that show on Today.
- **Dashboards.** The studio builds tiles over Gold; a different person approves; Consume shows only approved versions.
- **Deployment.** The Dockerfile builds the UI, then one uvicorn process serves UI and API. Volume at /data, keys and model mode in Railway variables, health check /api/health.

## Two traces
1. **A figure from file to dashboard:** file dropped, Landing, Pipelines build Bronze, Silver, Gold, Checks read Silver and open cases, studio proposes tiles, another person approves, Consume shows it, Map traces it back.
2. **An agent answer:** question, API checks route and company, loop reads memory and local passages, tools return totals, router picks tier and mode, egress masks and logs, model replies, guard replaces any untraceable figure, reply and memory are stored.

## Honest notes
- OpenAI voice is used only by the offline demo-video tool (`tools/video/narrate.py`), not by the running app; the diagram shows it apart. In the app, speech goes through egress to Google (free tier, development and demos).
- The diagram carries no source citations (this folder is not a Git repository); each box was checked against `sh_platform/` with graft.
- No key or .env value appears in the diagram.
