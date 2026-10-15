# Review K1: owner, sensitivity and topic on uploads

Reviewed: `sh_platform/v1/k1_classify.py`, `k1_access.py`, `k1_routes.py`, `k1.permissions.yaml`, the K1 edits in `c4_library.py`,
`c4_routes.py`, `ui/src/v1/c4/ContextBox.tsx`, `ui/src/v1/k1/*`, `tests/v1/test_k1.py`; traced through `file_context`, `i2_north`,
`catalogue_scan`, `p1_project`, `egress/gateway.py`, `egress/vault.py`. Probes run against the code (not read from the report).

Runs: `SH_MODEL_PROVIDER=off python -m pytest tests/v1 -q` -> 76 passed (0 skipped). `cd ui && npx tsc --noEmit -p .` -> 2 errors, both `Cannot find module '../p5/HandoverCard'` in `b5/OpsPage.tsx:4` and `f1/EngineerPage.tsx:14`; not K1's (P5 card not landed), K1 files type-check.

## Blockers

B1. Header-less table: values stored, previewed to the company and sent to the model. `k1_classify.py:123-128,165`.
Scenario: a CSV export without a header row, one data row `Zed Quill,C-1001,zed.quill@x,+65 6123 4567,500`. `scan_pii` treats row 1
as headers and scans only `rows[1:]`, so `found=False`, the proposal says "No personal data found. Keep as Open?", and `outline`
stores `columns=['Zed Quill','C-1001','zed.quill@x','+65 6123 4567','500']` in `index.json` (`item.preview`). With Open that file
is readable anyway; with Restricted-by-owner every company viewer sees those values in the lock preview (`LockedRow.tsx:95`), and
`ask_topic` sends them to the model (`_clean` strips digits and e-mails, not the name). With two data rows `pii.where` becomes
`column 3 (zed.quill@x)`, `column 4 (+65 6123 4567)`: values in `index.json`, in the proposal and in the owner's `pii.where`.
Fix: in `scan_pii` and `outline`, run `_cell_kinds(h)` over the header row; if any header cell matches (or contains `@` or 3+ digits)
treat the table as header-less: `where = f"column {c+1}"`, `columns = None`, and merge the header row into the scanned rows.

B2. First line of a text goes to the model and the preview as written. `k1_classify.py:166-169,211-212,231`.
Scenario: a memo starting `Dear Mr Zed Quill, NRIC S1234567A` (probe: `outline` returns that line). The NRIC marks the file as
personal, so the preview hides the heading, but `propose` still calls `ask_topic` with `heading` -> the model receives
`Dear Mr Zed Quill, NRIC SA`. The egress vault tokenises only *registered* names (`vault.py:21-24`), so an unregistered client name
leaves the plane. Same for a file whose first line has no detectable pattern (`Re: Zed Quill termination`): stored as the preview heading
and shown to everyone who sees the lock. The landing report admits this for file names only.
Fix (one line): in `propose`, `if not sure and model is not None and not pii["found"]` (a restricted file takes the rules' topic);
and in `outline` keep a heading only when it is a Markdown heading (`#`) or has no capitalised two-word run (`_ADDR`-style check),
else `None`.

B3. A denied request can be re-asked in a loop. `k1_access.py:160`, `LockedRow.tsx:101`.
Scenario: owner clicks Not now; the requester's row shows Request access again (state `denied` is allowed at `LockedRow.tsx:101`);
`request_access` de-duplicates only `state == "requested"`, so every click appends a new row to `access.json`, a new P1 comment and a
new Pulse card for the owner. Nothing in the tests covers deny-then-re-ask.
Fix: in `go`, treat the latest row for (item, requester) with `state == "denied"` and `decided_at` within 7 days as the duplicate
(return it); the UI then shows "Not shared just now" with no button until the cooldown passes.

## Should fix

S1. Self-approval by an admin when the owner has left. `k1_access.py:176-177,195`. A company_admin requests a left owner's
restricted file and approves their own request (`_may_answer` passes). Equivalent to the admin's `reassign` power, but it is recorded
as a normal approval. Fix: `if req["requester_id"] == viewer.account_id: raise Refused(409, "Give the file a new owner instead.")`.

S2. `iid` on a request is not checked against the requester. `k1_access.py:166-172`, `k1_routes.py:89`. Any string reaches
`p1.comment(plane, iid, ...)`; `_pid_of` -> `project_of` *creates* a project for an intent on first ask (`p1_project.py:108-116`).
A requester can post an `access` comment into a conversation/project they never opened. Fix: validate with `L._context_path(plane, iid)`
(exists) and the same visibility check `i6`/`c4_routes` use before passing `iid` on; otherwise drop it.

S3. Admin answers write the P1 trail as the owner. `k1_access.py:213`: `p1.answer(..., req["to"], ...)`, and `to` is the
owner's name even when a company_admin decided. Fix: pass `viewer.name` and let `request_access` address the comment to the
admin when `gone` (it already computes `to` that way, so only `answer` is wrong).

S4. Content oracles through upload. `c4_library.py:159-166`. `duplicate` fires on a *visible but locked* item with the same sha256
(confirms a locked file's exact bytes); `similar` fires when `_words(note)` equals the locked item's note (confirms its note word set).
Fix: compute `dup`/`similar` over `readable` items; locked items fall out of both lists.

S5. Expiry and the gateway path are tested in memory only. `test_k1.py:172-175` mutates the index in memory and calls `K.can_read`;
the HTTP read path with an expired grant is never exercised. `test_k1.py:108-119` uses a Stub that `router.route` returns unchanged
(`router.py:239-240`), so "digit-free prompt" tests `_clean`, not that the real call passes `send_model_prompt`. Add: write the expired
grant with `write_json_atomic` and assert `row(leela, ...)["locked"]`; one test that `ask_topic` with `get_model(...)` produces a
`vault_name` block when the heading holds a registered name.

S6. No test that a company_admin cannot read, tick, preview body text of, or approve for a Restricted item while the owner is
present. Priya (sponsor) stands in for "someone else" at `test_k1.py:152`; Arjun is both owner and the only admin in every test.
Add one assertion with a second admin or with Arjun as a non-owner admin.

## Notes

N1. `GET /api/v1/library/people` (`k1_routes.py:64-68`) hands every analyst the company directory with account ids. Scope it to
owners of at least one shared item, or to company_admin + sponsor.
N2. `clean_topics` (`k1_access.py:283-286`) accepts free text up to 3x40 chars that is shown to everyone who can see the item and
is searchable; a topic can carry a value. Acceptable as the owner's own words; worth a `looks_private` check later.
N3. `_live` (`k1_access.py:66`) compares ISO strings; fine while `_add_grant` writes them, fragile if a grant is hand-edited
without a zone. `datetime.fromisoformat` is the same length.
N4. `pulse_cards` is not yet wired into `p2_pulse._compute` (confirmed by grep): Pulse shows nothing until the shared edit lands.
N5. Logging and errors are clean: `log.warning` strings carry no values, `RunRegistry` records no prompts, `_answer` returns fixed
messages, `checked_name` echoes only the extension. `egress_log.jsonl` keeps bytes and sha256 only.
N6. Access checks hold everywhere I traced: `selected`/`lines`/`catalogue_scan`/`i2_north.document_passages` all pass `readable`
(mine/open/live grant); `shown` cuts a locked row to `PREVIEW`; `listing` skips a locked note; `_find` keeps private items at 404;
`change` leaves sensitivity/topic to `_mine` only, with `pii.reviewed` recorded by name and time; revoke is a fresh read of
`index.json` so it is immediate. No other module reads `library/files/` by path.

## Verdict

Not ready. B1 and B2 break the card's own promise ("never a value") on common inputs: a header-less export and a letter-style
document. B3 is a nuisance loop the owner cannot stop. All three are small, local fixes in `k1_classify.py` / `k1_access.py`; S1-S4
are one to three lines each. Re-review after B1-B3 and S1-S2 with the two added tests from S5.

Summary: personal data values leak via header-less CSVs (stored, previewed, sent to the model) and via a text's first line (sent to the
model; vault covers registered names only); a denied request can be re-asked endlessly. Access control, expiry, revoke, owner-only
lowering and the preview whitelist otherwise hold; tests are green but three paths pass without exercising the real route.

## Re-check after fixes

Run: `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_k1.py tests/v1/test_c4.py -q` -> 15 passed (twice; one earlier run errored
on every test at fixture set-up, the `copytree` of `data/`, and did not recur: a collision with another process, not the code).
Probes run against `k1_classify.propose` / `outline` and by reading `k1_access`, `c4_library.upload`, `LockedRow.tsx`, `p1_project.answer`.

B1 closed. `k1_classify.py:117-119,129-132,173`. Ids only (`C-1001`), e-mails only, one data row (`Zed Quill,C-1001,...`), one
date row, a header that looks like data (`Q1 2026`): all `columns=None`, `where=["column 3"]`, no value in the proposal. A real
header (`as_of,portfolio,market_value`) and a header-only file still show column names. Two gaps, ranked below (S7, S8).

B2 closed for the stated cases. `k1_classify.py:178-180,241`. `Dear Mr Zed Quill, NRIC ...` (one or two lines): restricted, heading
`None`, model not called (`sent == []` in the test). `Re: Zed Quill termination`: heading `None`. One gap, ranked below (B4).

B3 closed. `k1_access.py:27-31,99-101,173`, `LockedRow.tsx:37-45`. A declined request is the duplicate for 7 days whatever `iid` the
second ask carries (`go` matches on item + requester only, so no second P1 comment or Pulse card); `state()` reports `denied`, the UI
shows "Not shared just now" with no button; after the window `request` returns and a new row is made. A `revoked` or expired-grant
latest row is not cooling, so a fresh ask is allowed. Tested end to end in `test_b3_...`.

S1 closed (`k1_access.py:212-213`, tested). S2 closed (`:157-161`: `_context_path` checks the id shape and the folder before any P1
call; the test asserts no project folder appears). S3 closed as far as K1 can (`:228`, tested with the real `p1.answer`). S4 closed
(`c4_library.py:157`: `seen` is visible and readable; the owner still gets the duplicate warning; tested).
Nothing new opened by S1-S4: `answer` still refuses non-answerers at 404 before the self-check; dropping `iid` leaves the request itself
intact; the `similar` note is now always readable text.

Tests exercise the path. `test_s5_expiry...` writes the expired grant to `index.json` and reads through `GET /api/v1/library`.
`test_s5_topic_call...` goes `ask_topic` -> real `router.route` (asserted `("north","doc_read")`) -> `EgressModelClient` -> gateway with
a stub transport: `transport.calls == []` and the last egress log line is `vault_name`, so the block happens before any network call.

Known limit confirmed, downgraded to a note. A gone owner's P1 comment is addressed to the first admin by name
(`k1_access.py:163-165`); `p1_project.answer:265` lets only `c["to"]` answer. A second admin's decision still lands (grant and
`access.json` are written before `_p1`), only the P1 trail stays open and a warning is logged. Needs P1 to accept any admin for
`kind == "access"`; not K1's.

New findings

B4. A Markdown heading bypasses the B2 check. `k1_classify.py:178`: `ln.startswith("#") or not (...)` keeps any `#` line as is.
Probe `# Letter to Zed Quill, NRIC S1234567A\nbody`: restricted, but `outline.heading` (and so `index.json` `preview.heading`) holds the
name and the NRIC. The preview hides it only while `contains_personal_data` is true; once the owner marks it reviewed and lowers the
sensitivity, every company viewer sees the heading. `# Re: Zed Quill termination` (no pattern) is stored, shown and sent to the model
now. My own suggested fix in B2 caused this. Fix (one line): `if not _line_kinds(ln) and (ln.startswith("#") or not re.search(...))`.
Narrow (needs a `#` first line) but it is a value in `index.json`, so it stays a blocker.

S7. A names-only table keeps a name as a column. `k1_classify.py:119`. `Zed Quill\nAva Marsh\n`: `_headerless` sees no kind, `@` or
digits, so `columns=['Zed Quill']` is stored, shown in the lock preview and sent to the model. Fix: also treat the table as header-less
when every non-empty cell of row 1 matches the name-run pattern used at line 178 and row 2 has the same shape.

S8. Pre-existing, not from the fixes: `scan_pii` enumerates columns by the first row's length (`:131`), so a ragged file
(`a,b\n1,2,zed.quill@x\n`) leaves column 3 unscanned and proposes Open. Fix: iterate `range(max(len(r) for r in rows))`.

N7. Upper-case names (`RE: ZED QUILL TERMINATION`) pass the `[A-Z][a-z]+` run check and are kept as the heading. Add `re.I`.

## Verdict (re-check)

Not ready by one line: B4 puts a value into `index.json` through a `#` heading. B1-B3 and S1-S4 are closed and the new tests exercise
the real routes. Fix B4 (and S7 if cheap), add the `# Letter to ... NRIC` line to `test_b2_...`, and this lands without another round.
