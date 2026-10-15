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
