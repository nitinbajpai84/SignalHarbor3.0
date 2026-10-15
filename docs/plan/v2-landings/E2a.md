# E2a Document intake and revision detection

**Changed:** manager statements are registered once, kept untouched, read for fund, valuation date and status word, and a revision is linked to the statement it replaces.

**Files:** `sh_platform/v1/e2_intake.py`, `e2a_routes.py`, `e2a.permissions.yaml`, `tests/v1/test_e2a.py`.

**Contract:** `register(plane, file_path, viewer, source_code="manager_email", received_at=None, data=None, filename=None) -> document id` and `supersession_of(plane, document_id)`. Extras: `listing(plane, instrument_id=None)`, `detail(plane, id)` (with `chain`, oldest first).
- Original copied to `landing/originals/<sha256>__<name>` (same place E0c1 uses). Same bytes again returns the same id.
- Row in `documents`: type from the L3 classifier (`manager_statement`, `capital_call_notice`, else the folder), fund via `e2_match.resolve` (only an approved match sets `instrument_id`; otherwise `processing_status = needs_match`), valuation date from "valuation date / as at / valued" lines, `contains_personal_data` from the K1 scan. Source system `source_code` and access group "Manager statements" are created if missing.
- Supersession: same instrument and valuation date, not yet replaced, and (words amended/revised/restated in the first 80 lines, or a later `received_at`). Status: printed word "final" gives `final`; else `revised_estimate` if it replaces one; else `estimate`.
- Indexed for document search through `doc_index` (PDFs and pictures in the background).
- Tests: 4, all pass (`SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_e2a.py -q`), text fixtures, E2c stubbed.

**Routes:** `POST /api/v1/evidence/documents` {filename, data base64, source_code?, received_at?} (analyst, company admin); `GET /api/v1/evidence/documents?instrument_id=`; `GET .../{id}` (with chain); `GET .../{id}/original`.

**How to test on the demo:**
1. Seed Evergreen (E0e) so Evergreen Growth I and its approved alias exist.
2. Upload the Fund A statement (valued 30 Sep) with received_at 2 Oct: status Estimate, current.
3. Upload the amended statement (same date, received 9 Oct): status Final, the first shows as replaced.
4. `GET /api/v1/evidence/documents/{id}` shows both in `chain`.

**Known limits:**
- `organization_id` uses `e1_write.org_id(plane)` (a UUID), not the slug, as E1b's landing says.
- Documents are inserted by SQL (no writer card for `documents`); access by seat only, the `access_group_id` is recorded but not yet filtered through E1d (the contract has no document function).
- `register` raises ImportError if E2c is not installed (per Facts item 4).
- Scanned PDFs yield no text until OCR finishes, so their fund and date may be unset; the date falls back to the file name.
- Two same-fund same-date statements received the same instant: the later insert is treated as not later; use the amended wording.

**Wiring for the orchestrator:** none. Router and permissions auto-install by name.
