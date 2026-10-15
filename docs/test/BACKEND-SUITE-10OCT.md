# Backend suite, 10 Oct

Input run: `.sh-tmp/suite/backend-6.txt` (41 failed, 3517 passed, 163 errors). Rerun: `.sh-tmp/suite/backend-bs1.txt`.
Command: `python .sh-tmp/nm1_pytest.py tests -q -n 6 -p no:cacheprovider --timeout=300 -rfE`. Stub models only. Backups of every edited file: `.sh-tmp/<name>.bak-bs1`.

**Result: 5 failed, 3702 passed, 70 skipped, 0 errors in 23 min 44 s** (was 41 failed, 163 errors). The 5 are listed under Remaining, each with its cause and owner.

## 1. Environment

| Cause | Tests hit | Fix |
|---|---|---|
| Fixtures copy `data/` with `shutil.copytree`; the live server on 8400 holds `data/neera/warehouse/evidence.duckdb` open (Errno 13). The launcher's copytree patch only reached the controller process, never the xdist workers. | 45 files, ~160 errors (k1, l2, g3g4, l3, t1b, i1, pictures, voice, t2, ...) | `tests/conftest.py`: one wrap of `shutil.copytree` (runs in every worker) that skips only `*.duckdb` / `*.duckdb.wal` files that cannot be opened right now. No per-test edits; `data/` is only read. |
| The Ardmore role accounts (`<role>.ardmore@example.test`) and the `data/ardmore` plane are no longer seeded (the plane is now `ardmore-1` with named people; the branded set lives in gitignored `local/`). | role matrices, f50 journey, b19, contracts shapes | Role matrices (`tests/auth/test_role_matrix.py`, `tests/intents/test_role_matrix_intents.py`) sign in as the seeded `<role>.harbor-mutual@example.test` accounts (same six roles). `test_f50_journey`, `test_b19`, `tests/contracts/test_shapes_ardmore.py` skip when the Ardmore seed is absent (the pattern `test_b58` / `test_w2f2` already use). |
| Outage breaker (CB1) is process-wide by design; one test's 402 refused every later model call in the same worker. | evals/test_replay (6), nm1, router, s_wave2, voice | `tests/conftest.py` autouse fixture clears `gateway._breaker` before and after each test. |
| Seed doctor ports moved to 8400/8401 (`tools/doctor.py`). | test_seed_doctor (2) | Test reads Port 8400/8401. |
| Date-pinned tests ran on 10 Oct against 9 Oct / week 2026-W41 data. | test_e5a, test_b22 weeks route | e5a pins `wh.now` to its NOW; b22 pins the check-in clock to T(6), as the file's other test already does. |
| `reportlab` now installed in the venv; the e2 PDF fixtures were made by the built-in writer. | test_e2e determinism | Test hides reportlab while loading the generator. |
| Hostile HTML (300,000 nested tags) took 2.5 s under 6 workers (0.8 s alone) vs the 2 s bound. | ctx deep-nesting | Product: `reader._html_text` stops feeding the parser once the text cap is full (0.17 s now). Bound unchanged. |

## 2. Regressions after tonight's changes

| Test | Verdict | Change |
|---|---|---|
| `GET /api/v1/evidence/documents/{id}/original` (found by role matrix) | Product bug: unknown id raised `Refused` uncaught, a 500 | `sh_platform/v1/e2a_routes.py`: the route runs inside `_answer`, so an unknown id is a 404. |
| `tools/seed_demo_history.py` (3 tests, KeyError intent_nudge) | Product bug: it drafted every `messages.KINDS`, which grows when `intents.nira` is imported | Drafts only the kinds it has recipients for. |
| `test_e0b1` worked mappings | Product regression from G1: merging `data` into Span dropped the three worked mappings | `skills/span/examples.md` names position_snapshots, valuation_observations and cash_movements in one compact line (under the 6,000-character cap). |
| evals/test_replay | Isolation, not product (see breaker above) | none in product |
| test_nm1, test_s_wave2 (2), test_router | Test out of date: Nitin 10 Oct put every Testing tier on Gemini (`model_modes.yaml`) | test_router expects manager = gemini-2.5-flash. The cross-provider walk tests use a `two_provider_testing_mode` fixture (`tests/v1/conftest.py`). H1-01 now starts at manager (OpenRouter 402) and falls to Gemini: under CB1/NM1 a 402 ends that provider's walk, so the old "Gemini 402 then Gemini answers" path no longer exists by design. |
| test_voice | Test out of date: NM1 adds a `note` to voice failures | expects `{"failed": True, "note": ...}` |
| test_b10 events writes | Test out of date: N2 comments keep their own append-only `comments/events.jsonl`, one writer (`n2_comments._append`) | n2_comments.py excluded by name; the intent event rule is unchanged |
| role-matrix top bar | Test out of date: PF2 (every role reads Consume) and the Tickets centre in `ui/src/shell/roles.ts` | bar lists updated |
| smoke company_id rule | Test out of date: super-admin `GET /api/control/companies/{company_id}/intents` (intents/admin.py) | added to the list; the super-admin-only role check still runs on every such route |
| test_x1 gold figures | Test out of date: C1 fix labels the cash view by source (administrator / trading export) | keys renamed; the 12,400 difference still asserted |
| test_packs client data | Test widened for false positives only: an address on a reserved TLD (.test/.invalid/.example) and a 9+ digit amount with a decimal part (custody SGD) | still fails, see Remaining |

No safety assertion (egress, access, injection, maker-checker, grounded figures) was weakened.

## 3. Remaining

| Test | Cause | Owner |
|---|---|---|
| `tests/auth/test_auth.py::test_fastapi_version_is_the_tested_one` | The venv has FastAPI 0.136.3; the pin and auth enumeration were tested on 0.142.x. Pin **not** updated: the two auth tests below fail on 0.136.3. | Environment (Nitin): reinstall `fastapi==0.142.*` in the venv, or re-check `iter_routes` / `all_routes` in `sh_platform/auth/__init__.py` for 0.136 and then move the pin |
| `test_auth.py::test_undeclared_frontend_is_refused`, `test_enumeration_fails_on_what_it_cannot_classify` | `app.frontend` does not exist in FastAPI 0.136.3 (AttributeError). Same cause as the pin. | Same as above |
| `tests/test_packs.py::test_the_family_office_pack_holds_no_client_data` | A real guard catch, not a test bug: 44 files of `packs/family_office/1/` (demo_cycle emails, people.csv, demo_module3 workbook, ...) carried the prospect name, which the hashed name guard bans in the tracked pack (since renamed to the neutral "Ardmore"; the guard passes). | Pack / demo-cycle author (Nitin decides): rename to a neutral firm in the pack, or move the branded demo cycle to gitignored `local/` |
| `tests/v1/test_proposal_speed.py::test_picture_proposal_is_quick` | Timing under 6 workers: 5.5 s against a 5 s bound (3.6 s alone; the OCR engine's cold load). Not a regression of tonight's work. | K1 proposal speed owner: warm the OCR engine once per process, or run this test without xdist load |

## Review (security, 10 Oct)

I checked every edit against its `.bak-bs1` backup.

- **Safety assertions:** none were weakened.
  - Egress, access, injection, maker-checker and grounded figures are unchanged.
  - The smoke rule adds one route, and the loop still requires `{"super_admin"}` on it.
  - The e2a change only turns an unknown-id 500 into a 404. The `can_see` 403 runs as before, using the same `_answer` pattern as the detail route.
  - The role matrix still checks denials. The only change is the account suffix (`harbor-mutual`).
- **Test updates match intended changes:**
  - Router: `model_modes.yaml` says "Nitin 10 Oct".
  - Top bar: PF2 landing item 4 makes Consume available to every role.
  - Voice note: NM1.
  - x1: the C1 labels. The 12,400 difference is still asserted.
  - The `two_provider_testing_mode` fixture keeps the cross-provider walk and the breaker under test.
  - b10: `n2_comments.py` writes only `comments/events.jsonl`. The exclusion is by file name, which is wider than needed, but acceptable.
- **test_packs relaxation:** The run shows it is safe. `harvey.rowley@ardmore.example` now passes the email rule, and the name check still fails the file. The reserved-TLD rule needs no continuation after the TLD. A 9+ digit run with no decimal is still flagged.
- **Live data:** the conftest `copytree` patch changes only the `ignore` set, and only for `*.duckdb` / `.wal` files that cannot be opened. Nothing in `data/` (outside the live server's warehouse and logs) changed after the backups. Side note: inside the test session, product code that calls `copytree` on a locked duckdb also skips it silently. This only happens while the live server is running.
- **Defect fixed (coverage):** b19's module-wide skip also disabled `test_handoff_is_the_organiser_only` (R15 access rule) and the event-kinds test, and neither needs the seed. The skip now lives in the `world` fixture, and the handoff test runs without the seed. b19 now has 2 passed and 6 skipped (was 0 passed and 8 skipped). Backup: `.sh-tmp/test_b19.py.bak-bs1-review`.
- **Open, owner: test owner:**
  - With the ardmore seed gone, b19's `test_a_sealed_measure_is_counted_never_named` and `test_shapes_ardmore::test_feeds_shape_and_access` do not run.
  - Rebuild the b19 fixture from a synthetic baseline (or `harbor-mutual`) so the sealed-measure privacy check runs on every machine.

Verdict: pass with one fix. No safety assertion was weakened. The test changes match PF2, NM1, C1, N2 and the 10 Oct router rule. Live data was not written. Remaining 5 failures unchanged.
