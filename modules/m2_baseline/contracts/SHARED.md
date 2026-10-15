# Module 2 shared contract (all M2 packages code against this; A-042)

Everything lives in the company plane under `intents/m2_baseline/<baseline_id>/` and is written with
`sh_platform.jsonfile` (atomic write, strict read, `lock_for`). One baseline per signed charter.

Every value a person or an agent supplies is a **provenance value** (`domain/provenance.py`):
`{"value": ..., "mark": "stated" | "guessed" | "unknown", "by": "<person name or Lens or the pack>", "at": "<iso>",
"from": "<where: answer id, document title, pack, meeting>"}`. Unknown keeps `value: null`. A blank is never shown as known.

| File | Owner package | Shape |
|---|---|---|
| `baseline.json` | M2-P01 | `{id, charter_outcome_id, state: draft/requests/mapping/review/signed, created_at}` |
| `kpis.json` | M2-P01 | list of `{id, name, problem_ids[], priority, definition: prov, owners: {business, data, process: prov of a name}, governance: {personal: yes/no/not_sure, sensitive: bool, may_see: [names]}, tracking: prov of tracked_now/partly/not_tracked}` |
| `requests.json` | M2-P02 | list of `{id, owner_name, role, kpi_ids[], token_hash, state: sent/opened/answered/no_reply/in_meeting, sent_at, reminders: [iso]}` |
| `answers.json` | M2-P02 | list of `{id, request_id or meeting, owner_name, kpi_id, tracked_today, could_track, source, data_type (structured/unstructured/both), arrival, sla, dependencies, sample_doc_id, upstream: [{who, what}], in_between: [{who, step, manual}], downstream: [{who, what}]}`; each field a prov value |
| `process_map.json` | M2-P03 | `{kpi_id: {lanes: [names], steps: [{id, lane, text, order, manual, confirmed, from, state: proposal/validated/edited/removed, by}]}}` |
| `catalogue.json` | M2-P04 | `{sources, tables, fields, extractions, kpis}`: one list per template tab, columns exactly as `docs/specs`/the template `signal-harbor-data-catalogue-template.xlsx`, each cell a prov value |
| `signoff.json` | M2-P05 | owner confirmations per part, sponsor and head-of-data signatures, versions |

Notes on `answers.json` source rows (fix F):
- An old answer with one free-text `source` reads as one guessed row (named from the text, marked guessed); the old data type, arrival and SLA ride along.
- A system used by any restricted KPI (personal yes or not sure, or sensitive) is built from the open KPIs' rows only when there are any; otherwise it is personal. A shared source's "Who may see it" is the intersection of the `may_see` lists of the restricted KPIs using it (narrowest wins). Conflict versions come from open KPIs only.
- Cap (chosen): at most 60 rows across all KPIs in one answer save; the form itself takes at most 12 rows per field.
 through that package's `store/<area>.py` read function only. Until it lands, use a
fixture with exactly this shape.
