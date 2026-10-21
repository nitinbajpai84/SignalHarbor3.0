# Architecture diagrams

Each diagram is an Archify JSON spec plus its rendered HTML. Edit the JSON and re-render; never hand-edit the HTML.
Render: `node <archify>/bin/archify.mjs finalize architecture <name>.json <name>.html --quality showcase --json`.
A diagram with cited sources (sh-four-centres) also needs `--repo-root <git repo>`. Repo 1.0 is not a Git repository, so the 9 Oct render used a Git snapshot of the cited files (origin `https://local.invalid/signal-harbor/repo-1.0.git`, the revision pinned in the JSON). To re-render, rebuild that snapshot from the `sources` paths and update the revision.

| Diagram | Shows |
|---|---|
| sh-platform | Shared kernel and the three planes |
| sh-four-centres | As built 9 Oct: four centres (Intent, Action, Build, Consume) plus Map and Settings, agents North, Span and Lumen, router and egress, the per-company DuckDB plane; every box cites source |
| sh-three-centres | Intent, Build and Consume centres on one kernel (6 Oct, superseded by sh-four-centres) |
| sh-agent-egress | The single exit and its four guards |
| sh-m4-build | Build module |
| sh-packages | Package layout |
| sh-return-cycle | Notice, Think, Decide, Build, Run, Prove: the agent at each stage and the records it writes |
| sh-cycle-modules | Radar, Proving, Build chain and Consume views: routes, records and the exit, inside the three planes |
| sh3-detailed-architecture | 3.0 as built (21 Oct, revision 42418cf): people and the PWA, the app server, Harbor's thread runner and services, the five skill groups (North, Span, Flow, Lumen, Tally), the company volume, production-only Redis, worker and Postgres, and the outside; views for a file to an answer, a use case build, a model call and a signal to an Action card; every box cites source |
| sh3-cloud-targets | 3.0 at a customer: each Signal Harbor part mapped to AWS, Azure and no cloud (Docker Compose or Kubernetes on a VM), one view per target plus the DuckDB one-writer constraint |
