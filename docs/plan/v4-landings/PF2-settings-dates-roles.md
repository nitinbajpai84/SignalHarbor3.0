# PF2: Settings wording, signed register, company dates, Consume for all, SOP as Word

Fixes demo-guide findings 6, 7, 8 (role part), 10 and 11 (docs/guides/DEMO-GUIDE-10UC.md, "Found while writing").

## What changed

1. **Mode switch wording.** One sentence, `MODE_WORDS` in `ui/src/v1/router/ModeSwitch.tsx`: "Testing: free model tier, for trying things. Real use: the company's chosen models. This switch applies to everyone in the company." Settings > Testing or Real use shows it; the top-bar switch carries it as its tooltip and `aria-description`. "Made-up answers" is gone.
2. **Signed register.** Cause: `/api/company/register` (`sh_platform/graph/register.py`) built rows only from the 2.0 graph (charter, baseline, blueprint, prove). The 1.0 demo signs through Intent (`intents/<iid>/sow.json`), so it read "Nothing has been signed yet". The same route now also returns `records`: each signed intent of work (signer, date), its measures, each approved rule version (from the warehouse, read only when it exists) and the newest approved build plan per project. `RegisterPage.tsx` lists them in a "Signed records" table above the measure table. The subline reads, for example, "1 signed intent, 4 measures aligned, 0 fully released".
3. **Dates.** `ui/src/design/dates.ts` shows every instant in the company's one time zone. `/api/auth/me` returns `time_zone`, taken from the company profile's `time_zone` and set to Asia/Singapore when the profile has none. `useSession` sets it once. A date-only value, or a stamp with no offset, is shown as written and never shifts. Settings' own `stamp`/`dayLabel` and the register's signature hovers now use the helper.
4. **Consume for every role.** The participant row in `ui/src/shell/roles.ts` now includes `consume`. `route_permissions.yaml` gives participant read access to the 2.0 Consume routes (feeds, market, what-if, save and scenarios). Keeping a scenario and writing market briefs stay limited as before. The 1.0 Consume routes (c1, c2, c3, cx) already admitted participant. Figures stay filtered by each person's access on the server.
5. **SOP as .docx everywhere.** `k8_sop.to_docx` uses python-docx when it is installed. Otherwise it writes a valid minimal Word file with the standard library (zipfile and WordprocessingML). python-docx is not in the project venv. `/sop/download` now always returns .docx, and `?format=md` still gives Markdown. The Intent panel link is unchanged and now gets Word.

## Tests (run 10 Oct)

- vitest: dates, shell, s1, router, i6, registerPage: 10 files, 70 tests passed. Date consumers a5, e2, k3, k7 and design: 10 files, 55 passed.
- `tsc --noEmit`: clean.
- pytest `tests/graph/test_register.py tests/v1/test_k8.py`: 9 passed. This includes the new signed-records test (intent, 4 measures, rule, plan; a draft is left out; no warehouse is created) and the stdlib-docx test.
- pytest `tests/auth/test_role_table.py`: passed. In `tests/auth/test_auth.py::test_login_ok_and_me`, the expected payload now includes `time_zone`, and the test passes.
- These failures were already there and are not from PF2: `test_role_matrix` (no `participant.ardmore` seed credential) and three `test_auth` tests (FastAPI 0.136 against 0.142, `app.frontend`).

## Left open

- The seed stamps the intent signature "now" (`tools/seed_v3_demo.py` `_now()`), so "Signed" shows the seed day, not 3 Oct. That is a seed change, outside this card.
- Older intent screens (`ui/src/intents/*`) still format dates with their own UTC or explicit-zone code, not `design/dates`.
- The project page's intent .docx (`p1_project` via `t1_layout.to_docx`) still needs python-docx. It was not touched.

Backups: `.sh-tmp/*.bak-pf`.

## Review
Re-ran: pytest test_register + test_k8 9 passed; vitest design/shell/s1/router/i6 10 files 71 passed; tsc clean. Scope: out-of-card edits (auth routes, useSession, client.ts, route_permissions.yaml, register.py) are needed by the fixes. Open: seed signature date, ui/src/intents date formatting, project-page docx needs python-docx. Verdict: accept.
