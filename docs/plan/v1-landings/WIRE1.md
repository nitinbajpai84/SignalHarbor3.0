# WIRE1: five small jobs

1. **Flow (f1) edits from V1.md applied.** `ui/src/v1/f1/EngineerPage.tsx` (Composer, dropFiles, SpeakButton, useReadAloud), `f1/api.ts` (files, kindOf, readBase64), `f1_routes.py` (files saved with `i2_north.save_file`, body limit `MAX_TURN_BODY`, `N.Refused` returned as an error), `f1_chat.py` (`files` on `chat` and `ask`, `added_line`, `files_now` with its trim). f1 test now uses the label "Your message"; no change to Composer.
2. **X5 accept.** `x5_extract.accept` sets status to review while any check still fails after the correction. Test line added in `tests/v1/test_x5.py`.
3. **A1 approve.** After the scope is agreed, `B3.draft(plane, iid)` runs once more (guarded, logs and carries on if it fails; b3 keeps person edits). Test line in `tests/v1/test_a1.py` checks the sheet version is 2. Note: the redraft runs without a model runtime, so unedited rows take the rules wording.
4. **b4_formula.py line 116:** raw string, warning gone.
5. **i6.** A real bug: the "Hand to the architect" link (and the download link) used the URL id, empty on `/centre/intent` after the first message. They now use `chat.id`, so the link is `/centre/intent/<iid>/sow`. Test unchanged.

Extra: `tests/v1/test_f1.py` patched `sys.modules` for `room` but not the package attribute, so it failed in the full suite order; now patches both.

Run: `tests/v1` 55 passed; `tsc --noEmit` clean; vitest f1 and i6 pass.
