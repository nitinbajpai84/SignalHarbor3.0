# Industry packs

One folder per industry (`packs/<industry>/<version>/`): problems, glossary, measures, feeds, column synonyms, process map defaults, market briefs. Pack content is a suggestion of what others in the industry usually do; it is never a company's own definition.

The insurance and asset-management packs come over from the earlier repo in phase 1.

## Placeholder: industry knowledge connectors (decision O-5, not designed yet)

Over time each industry's agents should learn from outside sources: for finance, research repositories and a market data terminal. The intended shape, to be designed after modules 1 and 2:

- A connector is a tool in the tool registry, declared per industry pack (`connectors.yaml`), and switched on per company.
- It is inbound only: material comes in through the egress gateway, marked as outside material. No company data goes out in the request.
- Licensed data stays under its licence: it is fetched per company that holds the licence, never copied into the pack.
- What a pack learns across companies comes only through the distillation gate (structure only, opt-in, reviewed).
