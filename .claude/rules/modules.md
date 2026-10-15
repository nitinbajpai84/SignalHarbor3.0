---
paths:
  - "modules/**"
  - "ui/src/modules/**"
---

# Module boundaries

- Each module owns one folder under `modules/`: `manifest.yaml`, `api/`, `agent/`, `tools/`, `ui/`, `tests/`, and its own `CLAUDE.md`.
- A module may import from `platform/` and from `packs/` through the pack loader. It may not import from another module. Modules talk only through their outputs (charter, catalogue) stored in the company plane.
- A module that is switched off for a company is invisible and unreachable: no tile, no route (refused), no agent, no tools.
- Each module starts from the previous module's output, or from the same output uploaded by the customer.
- Signed content is read-only. A new draft never overwrites a human edit; it records a proposal beside it.
- New shared code goes in `platform/` only when a second module needs it.
