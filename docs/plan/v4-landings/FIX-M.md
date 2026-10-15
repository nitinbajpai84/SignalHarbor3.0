# FIX-M Managers (UC3, UC7)

## What changed
- k5_managers.py: `_bdays_after(a, b)` counts weekdays in (a, b]. Used for inbox late, received late, `earlier_missing` and the follow-up wording ("N business days overdue"). D June at 9 Oct = 63, H2 Aug = 6 (asserted in tests).
- Follow-up draft: greeting is "Dear Hana Sato (Cedarpoint Ventures)," when a contact is found, else "Dear {manager} team,". Response also carries `contact`.
- Contact source: the core model (evidence-to-action-mvp.dbml) has no contacts table, so it is read from `instrument_identifiers` where `identifier_type = 'manager_contact'`, `mapping_status = 'approved'`, on any fund of the manager (value = full name).
- What changed since the last meeting: new `revised_value` items ("X value for 30 Jun 2026 was revised from A to B USD, recorded 8 Oct 2026") from valuation_observations rows that supersede an older one, with a source chip to the evidence document (link `/centre/action/evidence/{id}`, or the valuation label); statements received late say "N business days late"; statements that fell overdue after the meeting appear as `late` items.
- Profile: each fund `last_value` has `status` (via k4_office `_status`, so Stale after 90 days) and `status_word` (Official, Revised, Estimated, Unverified, Stale). Documents list now has `kind`, date (`at`) and a one-passage `passage` from doc_index, only for files the viewer can read (locked files show the preview only).
- UI: inbox shows status word and "business days"; manager page shows document kind and passage. api.ts types extended.

## See it on screen
Action > Managers (inbox): "63 business days late" style wording and the status word after each last value. Consume > Managers > a manager: Diligence documents with kind, date and quoted passage; "Show what changed" lists revised figures and late statements. "Draft a follow-up" opens with the contact name.

## Tests
- pytest tests/v1/test_k5.py: 15 passed (3 existing assertions updated from calendar to business days; 3 new tests).
- ui: npx tsc --noEmit clean; vitest src/v1/k5: 8 passed (2 expectations reworded to "business days").

## Wiring for the orchestrator (seed)
- Store the contact per manager: one `instrument_identifiers` row on at least one of the manager's funds: `identifier_type='manager_contact'`, `identifier_value='Hana Sato'`, `mapping_status='approved'`, with any valid `source_system_id` (e.g. a "Manager contacts" internal source). Cedarpoint Ventures needs it on a Cedarpoint fund (D or E).
- Revised values need the revised valuation row to carry `supersedes_valuation_id` and `evidence_document_id` (for the source chip) and `recorded_at` after the meeting.
- Diligence docs must be in the library (c4_library) naming the manager, with kind DDQ/newsletter/meeting note; the passage comes from doc_index.
- Backups: .sh-tmp/*.bak-fixcp.

## Review
Verdict: accepted with small fixes. Diff against .sh-tmp/*.bak-fixcp read in full; tests/v1/test_k5.py 15 passed, npx tsc --noEmit clean, vitest src/v1/k5 8 passed, after the fixes below. No file outside the list was touched by fix M (the other .bak-fixcp files belong to other fixes). Money stays Decimal (`_money` -> Decimal string, no arithmetic); k5.permissions.yaml and k5_routes.py are unchanged (default-deny holds); screen copy is plain ("63 business days late", "Dear Hana Sato (Cedarpoint Ventures),", "revised from A to B USD").

Changed in review (same files):
- `_revised_values` skipped rejected or pending valuations: a `supersedes_valuation_id` row whose `approval_status` is not approved/approved_official/confirmed (the same set e3_calc uses) is no longer shown as "was revised from A to B".
- `_documents_with_passages` now takes the readable `raw` items `_library` already returns instead of re-reading the library index and re-checking access a second time. Same access filter, one read.
- ui/src/v1/k5/ManagerPage.tsx was written with CRLF line endings; restored to LF like the rest of the folder.

Open items for the orchestrator:
- `.sh-tmp/api.ts.bak-fixcp` holds the k4 api.ts (fix C/P overwrote it), so there is no backup of the k5 api.ts before fix M; the k5 change there is additive types only (`status_word`, `contact`, `DiligenceDoc.kind/passage`).
- Profile timeline has no days-late figure (it lists statements and revisions only); the late figure in business days appears in the inbox, the follow-up and "what changed". Add it to the timeline only if the screen spec asks for it.
- Document date shown is the library upload date, not the document's own date; the seed's upload timestamp is what the screen shows.
- Not run against 10UC seed data (seed is still being written).
