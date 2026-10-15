# Insurance pack (template insurance@1) -- what each file is for

V3-03 brief item 8. This file describes the pack; it is not itself a contract and gates nothing
(the same status as glossary.yaml -- see that file's header). Every content file in this pack is
pack content pending practitioner review, not an approved business rule (see
`packages/V3-03/report.md` for the Open Questions a practitioner should resolve first).

## The one rule that applies to every file here

**Nothing in this pack is a business rule.** No file carries a target, a threshold or a company's
own decision -- those live in the Intent Centre / `settings/*.cmo.yaml` once a customer sets them
(CLAUDE.md rule 4). Every `typical_actions` / `industry_defaults` entry is labelled "Industry
practice (suggestion)" (ND-35): North may describe how insurers typically implement or track a
KPI, but nothing takes effect until a person confirms it. Anything this pack is unsure of carries
`status: proposal` and a line in the builder's report's Open Questions, never a silent guess.

## Files

| File | What it is for | Reviewed by |
|---|---|---|
| `template.yaml` | The pack's manifest: id/version/status, file list with sha256 (integrity, `scripts/sh/template_check.py`), open questions. | Reviewer agent (author != reviewer), before `status: approved`. |
| `glossary.yaml` | Term definitions for North's context graph (Term nodes) -- what APE, persistency, lapse vs surrender vs free-look etc. mean in this industry. | A practitioner (insurance domain expert), then the reviewer agent for citation/structure. |
| `kpi_tree.yaml` | The 18 KPIs from `docs/signal-harbor/cmo-proof/kpis.json`, with sourced `drives` edges and levers. No values, no targets. | A practitioner, for whether the drives edges and levers are the right ones; the reviewer agent for "no values/targets" compliance. |
| `problems.yaml` | 17 problem templates by role (question, decision, kpi_ids, typical industry actions, what the customer must decide). | A practitioner, for whether these are the right 17 problems and the right KPIs/actions per role. |
| `industry_defaults.yaml` | One "Industry practice (suggestion)" entry per KPI: how insurers typically define/window/break down it, and which of kpis.json's own open questions block it. | A practitioner, for accuracy of the industry-practice variant; must carry a source or it is invalid. |
| `feeds.yaml` | The logical feeds (policies, agents, leads, campaigns, claims, cep_sends, customers) a workspace needs, field by field, with which KPIs need which field and the fallback when a required field is missing. | A Head of Data / data architect, for whether the feed/field list matches a real company's systems; a practitioner for the KPI linkage. |
| `column_synonyms.yaml` | Known source-system spellings for each feed field, seeded only from this repo's own discovery profiles and contracts. | A Head of Data, when onboarding a real source whose columns don't match the canonical names. |
| `market_briefs/{singapore,malaysia,indonesia,india}.md` | Short, dated, cited notes on who regulates/represents the industry in each market -- no figures without a public source. | A Market Intelligence agent or practitioner with access to the cited publications, to add dated figures with their own citation. |
| `intent_examples.yaml`, `generator.yaml`, `roles/`, `skills/` | Pre-existing pack files, not touched by V3-03 (out of this package's OWNS, or already in place). | Unchanged from prior packages. |

## Tests

`tests/test_insurance_pack.py` checks every file here loads, every `kpi_id` referenced anywhere
in the pack exists in `docs/signal-harbor/cmo-proof/kpis.json`, every `industry_defaults.yaml`
and `problems.yaml` entry carries a `source`, no key named `target`/`threshold` carries a
non-null value anywhere in the pack, the glossary has 100+ terms with no duplicate `term`, every
`column_synonyms.yaml` regex compiles, and every `feeds.yaml` required field references a real
KPI id. It does not check that any individual fact is *correct* -- that is the practitioner
review this pack is built to wait for.
