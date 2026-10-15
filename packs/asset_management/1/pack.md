# Asset management pack (template asset_management@1) -- what each file is for

V3-13. This file describes the pack; it is not itself a contract and gates nothing. Every content
file in this pack is PACK-DEFAULT content written by a builder agent from general
asset-management practice, pending practitioner review -- not an approved business rule (see
`packages/V3-13/report.md` for the Open Questions a practitioner should resolve first). The
template's status stays `proposed` (OQ-5).

## The one rule that applies to every file here

**Nothing in this pack is a business rule.** No file carries a target, a threshold, an industry
figure or a company's own decision -- those live in the Intent Centre once a customer sets them
(CLAUDE.md rule 4). Every `typical_actions` / `industry_defaults` entry is labelled "Industry
practice (suggestion)" (ND-35). Anything this pack is unsure of carries `status: proposal` and a
line in the builder's report, never a silent guess.

## How this pack differs from insurance@1

- **No KPI catalogue.** Insurance KPI ids (K01..K18) come from
  `docs/signal-harbor/cmo-proof/kpis.json`. No such catalogue exists for asset management, so
  the ids here (`kpi:aum`, `kpi:net_flows`, ...) are pack-local and `kpi_tree.yaml` is their only
  definition.
- **Three of twelve feeds have a source.** Only `portfolios`, `instruments` and `positions` are
  backed by a source contract (`contracts/sources/asset_management/awm_*.source.yaml`). The other
  nine feeds are proposals.
- **No numbers.** `industry_defaults.yaml` has `window: null` on every entry and no industry
  range; the market briefs carry no figures.
- **No `generator.yaml`.** No synthetic generator for asset management exists to point at.

## Files

| File | What it is for | Reviewed by |
|---|---|---|
| `template.yaml` | The pack's manifest: id/version/status, file list with sha256 (`scripts/sh/template_check.py`), open questions. | Reviewer agent (author != reviewer), before `status: approved`. |
| `glossary.yaml` | 100+ term definitions (AUM, net flows, TER, share class, distributor, mandate ...). | A practitioner (asset management domain expert). |
| `kpi_tree.yaml` | 18 KPIs with `drives` edges and levers. No values, no targets. | A practitioner, for whether the edges and levers are right. |
| `problems.yaml` | 17 problem templates by role (question, decision, kpi_ids, typical industry actions, what the customer must decide). | A practitioner, for whether these are the right problems per role. |
| `industry_defaults.yaml` | One "Industry practice (suggestion)" entry per KPI: how managers typically define it, and what the customer must decide. | A practitioner; an entry without a source is invalid. |
| `feeds.yaml` | The twelve logical feeds a workspace needs, field by field, with which KPIs need which field. | A Head of Data, for whether the feed list matches a real company's systems. |
| `column_synonyms.yaml` | Known source-system spellings for each feed field, seeded only from this repo's own source contracts. | A Head of Data, when onboarding a real source. |
| `process_map_default.yaml` | The default as-is swimlane from client order to board report. Every step is a proposal. | A practitioner or the company's own operations lead. |
| `market_briefs/{singapore,malaysia,indonesia,india}.md` | Short notes on who regulates and represents the industry in each market -- no figures, not verified this session. | A Market Intelligence agent or practitioner with access to the named bodies' publications. |
| `intent_examples.yaml`, `roles/`, `skills/` | Pre-existing pack files, not touched by V3-13. | Unchanged from prior packages. |

## Tests

`tests/test_asset_management_pack.py` checks every file loads, every `kpi_id` referenced anywhere
in the pack exists in `kpi_tree.yaml`, every `industry_defaults.yaml`, `problems.yaml` and
`feeds.yaml` entry carries a `source`, no key named `target`/`threshold`/`window` carries a
non-null value, the glossary has 100+ terms with no duplicate, every `column_synonyms.yaml` regex
compiles, `feeds.yaml` and `industry_defaults.yaml` agree on the `customer_decides` fields, the
manifest in `template.yaml` matches the files on disk, and the gap report and Intent Centre
loaders actually return this pack's problems. It does not check that any individual fact is
*correct* -- that is the practitioner review this pack is built to wait for.
