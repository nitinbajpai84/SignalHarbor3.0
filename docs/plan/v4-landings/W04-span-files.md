# W04 Span chat takes files

**What changed**
- `b6_routes.py`: new `POST /api/v1/build/p/{pid}/chat/files` {name, data base64} -> {name, path, kind} (needs read access to the project, 400 on bad base64, type and size checks of the library). `POST .../chat` now passes `files` (names) to `S.chat`.
- `b6_span.py`: `attach()` stores the file in the library (`c4_library.upload`, ticked for the project's intent, indexed in the background, as North's). `chat()` takes `files`: a turn with files and no "add a table" request is answered from the files (`search_documents`, top 3 passages, or an honest line); the person's turn shows "(attached: name)". The model path now gets the intent-scoped `search_documents` (`iid` passed to `span_registry`), so Span reads only the files ticked for this project.
- `ui/src/v1/b6/BuildPage.tsx`, `api.ts`: the composer holds files (drop on the box), uploads each one, then sends the turn with their names. Pictures and PDFs stay "name only", as in the shared composer.

**How to see it** Build > a project > drop a .csv/.txt/.docx on the Span message box, ask "when does the administrator send valuations?", Send.

**Tests** `tests/v1/test_b6_files.py` (4) and `tests/v1/test_b6.py` (9, unchanged) pass; vitest `ui/src/v1/b6` 11 pass (2 new in `chatFiles.test.tsx`); `tsc --noEmit` clean.

**Notes** Uploads are private to the uploader (library default), so a colleague asking Span does not read them. The company-wide `search_documents` of Span's model path is now limited to this project's ticked files (per the card). Backups: `.sh-tmp/*.bak-W04`.

**Review**
Verdict: accept. Re-ran tests/v1/test_b6_files.py + test_b6.py (13 pass) and vitest ui/src/v1/b6 (11 pass). Scope held: chat route, chat code in b6_span, ui/src/v1/b6 only; routes reuse i2 _decode/_json_body, uploads go through c4_library as North does. Wording plain, no game words. Open items: uploads default private so colleagues do not get answers from a teammate file (by design, worth a product call); Span model path now searches only ticked project files (as carded); no live browser check done.
