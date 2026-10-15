# Review of L2 "Proposed changes (accept or not)"

Reviewed: `sh_platform/v1/l2_proposals.py`, `l2_routes.py`, `l2.permissions.yaml`, the L2 edits in `i6_chat.py`, `a1_chat.py`, `f1_chat.py`, `c3_chat.py`, `ui/src/v1/workbench/{proposals.ts,ChangeBar.tsx}`, `tests/v1/test_l2.py`, against the card (`docs/plan/V1-BUILD.md`, "### L2") and the landing note.

## Verdict

**Not safe to restart the demo yet: two blockers, both small fixes in `l2_proposals.py`.** The storage, access and concurrency design is sound; the holes are in what a normal next message in the chat does to a pending proposal.

Test suite (`SH_MODEL_PROVIDER=off python -m pytest tests/v1 -q`): 176 passed, 1 failed in 7 min 20 s. The one failure is `test_proposal_speed.py::test_picture_proposal_is_quick` (9.8 s vs 5 s), not L2's (see the last section). All eight `test_l2.py` tests and the adjusted i6a/a1/f1/c3 tests pass.

## Blockers

### B1. A pending proposal is silently thrown away when the agent proposes anything else before the person decides

- `sh_platform/v1/l2_proposals.py:153-155`: `propose` marks every pending proposal for the same document `replaced`.
- `sh_platform/v1/i6_chat.py:111`: the prompt says "sow_patch holds only the sections you add to or change", so the model's next patch is incremental and does not repeat the earlier one. Same shape for Span (`a1_chat.py:366-374`) and Lumen (`c3_chat.py:340-346`).
- `sh_platform/v1/l2_proposals.py:269-286`: the model only gets a digit-free handle ("North proposed changes to the kpis Net worth"), never the content, so it cannot re-send it. `propose_patch` also diffs against the live SOW (`i6_chat.py:640-645`), which does not contain the pending change.

Failing scenario (the demo's own step 1): Arjun says "Net worth by entity every month". North proposes the KPI and ends "Who reads it? I have proposed 1 thing to change; say yes to accept...". Arjun answers the question instead of saying yes: "The board, monthly." North proposes `goal.readers`; the KPI proposal becomes `replaced`. Arjun says "yes": readers land, Net worth is gone, no trace, no comment. The ChangeBar simply changed its text in between.

Fix (shortest): delete the replace loop in `propose` and let several proposals per document stack; `resolve_words` and `pending` already handle lists and "yes" accepts them all in `at` order. If the stacked "before" text is then slightly stale in the ChangeBar, that is cosmetic. (Alternative: put the pending proposals' `changes` into `facts()` so the model re-sends; more tokens, more model dependence.)

### B2. A message that starts with "No" (any length) turns the pending proposal down

- `sh_platform/v1/l2_proposals.py:236,242-243`: `_NO` is checked first and has no length cap; `_YES` is capped at eight words.

Failing scenario: North's reply is "Do you have a benchmark figure for this? I have proposed 2 things to change; say yes to accept, or tell me what is wrong." Arjun answers "No, we have never measured it." Both proposals are rejected with that sentence as the reason, the SOW stays empty, the ChangeBar disappears, and North's next turn is told the person turned its KPI down. Same in Flow: "No, the field is `acct_no`" rejects before the model reads it (`f1_chat.py:409`, `435`).

Fix (one line): cap `_NO` the same way (`len(t.split()) <= 8`) or require the explicit words (`not this|reject|turn it down|wrong`) for anything longer than a bare "no"/"nope". The "I have proposed ... say yes" tail makes a yes/no answer to the agent's own question the most likely next message, so this will be hit in a walk-through.

## Should-fixes

1. **Flow's accepted proposal overwrites the engineer's hand edit of the same row.** `f1_chat.py:374-387` re-reads the row and calls `apply` -> `M.edit_row` with the model's values without comparing the proposal's `before` with the live cell; `b3_routes.py:65` (`PUT .../rows/{n}`) lets the engineer edit the row meanwhile. Scenario: Flow proposes `rule = "sum by entity"`; the engineer fixes the rule by hand on the sheet to "sum by entity, excluding trusts"; later says "yes" to settle something else; the hand edit is replaced. i6 has the snapshot protection; a1/c3 have no hand-edit path, so only f1 needs it: refuse with 409 ("the row changed since Flow proposed this") when a `before` no longer matches.
2. **Signed brief and signed build pack are still writable through accept** (`c3_chat.py:349-358`, `f1_chat.py:374-387`): neither checks `P1.signed`'s artefact state (`p1_project.py:198`). i6 and a1 check their own record state. The chat paths had this hole before L2; L2 adds a second path and a button that offers Accept on a signed document. One check in `L2.accept` on the project artefact state for `DOCS[document][1]`, plus marking pending proposals `replaced` on sign, closes both.
3. **"applying" is not what the comment says it is.** `l2_proposals.py:193-197` reverts to `pending` on any exception "nothing was applied", but i6 raises after its write if `_snapshot` fails (`i6_chat.py:668`) and f1 after `edit_row` if the record write fails (`f1_chat.py:385-387`); a re-accept then re-applies (idempotent by name match for i6/a1/f1 today, not guaranteed). A real crash leaves `applying` forever: hidden from `view()` and `pending()`, never replaced, never swept (`_write` keeps it). Minimal: show `applying` rows in `view()` with a Retry, or treat `applying` older than a minute as pending in `_read`.
4. **Model-off fallback applies at once.** Agreed for the parsed words of the person, but two things on that path are not the person's words and still land unasked: pack-suggested KPIs (`i6_chat.py:822`, `N.pack_suggestions`) and Span's blueprint default data model (`a1_chat.py:440-441`, filled whenever no proposal is pending, model on or off). Pre-existing; note it in the landing note as a known limit rather than "the person's own input".
5. `_YES` matches "ok"/"okay"/"approved" at the start of any sentence up to eight words: "Approved by the board last year" accepts. Fold into the B2 fix (a yes must be the whole short message).

## Nits

- `l2_routes.py:37-39`: `listing` returns `{pending: [], recent: []}` for any well-formed unknown intent (no 404); `viewer` is unused there.
- `l2_proposals.py:204-207`: `reject` writes twice (claim, then set); a crash in between leaves `applying`. One locked update is enough.
- `l2_proposals.py:74-77`: `replaced`/`applying` rows never age out of the file; only the 200-cap on settled ones.
- `l2_proposals.py:222-227`: the comment's line is found by a substring of the first changed label over every line ("Net" matches more than one); harmless, sometimes the wrong line.
- An intent with no project is "full" for every company member (`g1_access.py:130-133`), so anyone could accept there; the chat already works that way, and P1 creates the project on the first chat, so no live exposure found.
- `apply_proposal` in i6 overwrites cells of a row the person added by hand (no snapshot twin, `i6_chat.py:281`) if the model's patch names the same row. Pre-existing merge semantics.

## Checked and found sound

- **No sign-around.** Proposals live only in `proposals.json`; nothing outside L2 reads it (grep: P1 `document`/export, K2, doc_tools, Pulse, the sign checks all read the SOW/design/mapping/brief records). `test_a_pending_proposal_is_not_document_content` covers the SOW. `payload` never leaves the server (`_public`).
- **Access.** `l2_routes.py` is picked up by `v1/__init__.py:30-31` so `G1.intent_gate` runs: GET at "read", POST at "full"; `_OPEN_PATHS` does not match `/proposals`. `_writer` re-checks the document's writer role, which equals the roles the matching chat route allows (a1: admin/analyst; c3: admin/sponsor/analyst; f1: the data-engineer seat), so the chat-word path and the button agree. Non-member 403 is tested.
- **Double apply.** Claim under the file lock, apply without it, second accept gets 409 (`test_two_accepts_at_once_apply_once`). Engine locks are per-file RLocks; a1/c3/f1 call `resolve_words` while holding their own record lock and re-enter it in `apply_proposal` safely.
- **Person's edits (i6).** `_TL.kept` plus `_snapshot(..., kept)` keep the person's cell and North's old value in the snapshot; tested before and after an accept.
- **Digits.** `tail(n)` is program-counted and appended after the model guard; `line()` strips digits before the handle reaches the model; `summary` is program-written. No model-written id reaches the reply.
- **UI.** `useProposals` reloads the view after each call and shows the server's message on 403/409; `ChangeBar` renders nothing with no proposals.

## The timing test

`tests/v1/test_proposal_speed.py::test_picture_proposal_is_quick` is **not caused by L2**. It times `k1_classify.propose` (the upload classifier, a different "propose") reading a 1200x900 PNG through `ocr_local`; L2 touches neither file (grep for `l2`/`L2`/`proposal` in `k1_classify.py`, `ocr_local.py`: only K1's own names). Run alone on this box it took 10.7 s (while the suite ran beside it), so it is OCR time on this machine, not a regression from this card.
