# Module 2 (Baseline) enhancements: plan (Nitin, 4 Oct 2026)

**Goal:** what is signed off is ready to build. Module 2 ends with two signed, downloadable documents: the **business glossary** and the **data catalogue** (technical definitions and governance inside it). Every ambiguity is raised and settled, or knowingly accepted, before the signature. Lens does the work from what the business uploads; people review.

## Packages
| ID | What | Depends on | State |
|---|---|---|---|
| M2-AGENTS | Why Lens does not reply; pre-read step ("Give Lens what you already have"); Lens fills drafts from documents and pack; Lens's own conversational block; Nira small at the side | - | building |
| M2-GLOSSARY-DATA | Demo company's raw glossary and technical note with planted ambiguities, answer key, seed | - | building |
| M2-E2 | Business glossary: built by Lens per measure; import of a provided glossary; existing versus new comparison with assumptions; review; download | contract below | start now |
| M2-E3 | Governance view: who may see each measure and field, personal data, in one place and in the catalogue; download sheet | contract below | start now |
| M2-E1 | Technical definition per measure (source, table, fields, calculation) and the ambiguity list; Lens drafts both; owner confirms | M2-AGENTS | after M2-AGENTS lands |
| M2-E4 | Sign-off gate "ready to build" (no open ambiguity, technical definition confirmed, glossary reviewed, governance decided); sign both documents; one download bundle; hand-off carries them | E1, E2, E3 | last |
| CRITIC | Customer critic on the live app | E4 | last |

## Shared contract (all packages use these names)
- **Technical definition**, on the measure record: `technical = {sources, tables, fields, calculation, filters, grain, period, currency_basis, notes}`. `sources`, `tables`, `fields` are ids of catalogue rows; the rest is plain text. Every part carries the existing provenance mark (stated, guessed, unknown) and where it came from.
- **Ambiguity**, a list on the measure: `{id, kind, text, question, where, raised_by, status, resolution, by, at}`; `status` is `open`, `settled` or `accepted`; `kind` is one of `definition`, `period`, `currency`, `owner`, `source`, `calculation`, `threshold`, `governance`, `conflict`, `other`.
- **Glossary entry**, one per measure in the baseline's `glossary.json`: `{kpi_id, term, aliases, business_definition, owner, frequency, who_may_see, personal, change, previous, assumption, source_document, reviewed}`; `change` is `unchanged`, `changed` or `new` against a provided glossary (`new` for all when none was provided); `previous` holds the provided wording.
- **Governance** stays where it is (measure: personal, sensitive, may_see; source: contains personal data; field: personal data class). The governance view is derived, never a second store.
- Privacy rules do not change: restricted measures, fields and documents stay hidden from people who may not see them, in every view, download and hand-off.

## Rules for every package
Reuse first (extend the catalogue, proposals, provenance, sign-off, xlsx export, context documents; never a second implementation). Tests first. Independent review, one fix round. No push. Synthetic data only.
