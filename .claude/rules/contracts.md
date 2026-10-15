# Contracts and specs are the source of truth

- Specs live in `docs/specs/`; decisions in `docs/decisions.md`. Read the spec section for your feature before writing code.
- Never invent a table, column, threshold, business rule, role or API shape. If it is missing, write it under "Open questions" in your report and stop that part.
- A module's routes, screens, agent and tools are declared in its `manifest.yaml`. Code that is not declared there is not part of the module.
- Permissions per route are declared, and a route with no declaration is refused (default deny).
- Numbers an agent states must trace to a recorded fact; otherwise the screen says it cannot be worked out and names what is missing.
