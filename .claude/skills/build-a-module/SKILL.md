---
name: build-a-module
description: How a Signal Harbor module is structured and built. Use whenever creating or changing anything under modules/, adding a module screen, route, agent or tool, or wiring a module to the entitlement switch.
---

# Building a Signal Harbor module

## Folder

```
modules/<mN_name>/
  manifest.yaml   id, title, agent, routes, screens, tools, pack sections read, inputs, output, depends_on
  CLAUDE.md       rules specific to this module
  api/            FastAPI router, registered from the manifest
  agent/          the module's agent: instructions, context pack builder, evals
  tools/          tools the agent may call; read-only; registered in the tool registry
  ui/             React screens for this module
  tests/          unit, isolation, two-industry and empty-company tests
```

## Rules

- Everything the module exposes is declared in `manifest.yaml`. The platform loads routes, screens, agent and tools from the manifest only when the company's entitlement for this module is on.
- Import from `platform/` and the pack loader only. Never from another module.
- Read company data only through `platform` helpers that resolve the signed-in company. Never build a path from request input.
- Every model call goes through the agent runtime, which goes through the egress gateway.
- Agent tools return counts, totals and field names, never rows.
- The module's output (for example the charter or the catalogue) is written to the company plane and is the only thing the next module reads.
- Signed content is read-only; drafts never overwrite human edits.

## Definition of done for a module feature

- Spec feature id cited in the code comment and the test name.
- Tests pass for two industries, an empty company and a solo user.
- Screen checked in its five states.
- Reviewed by `sh-reviewer` (and `sh-security-reviewer` / `sh-ui-reviewer` where they apply) and landed with `/ship`.
