# FIXE1: rights found by UC6 and UC8 (12 Oct)

Five small fixes. Nothing else widened.

| Finding | Fix |
|---|---|
| Owner (Mei) and sponsor (Daniel) cannot hand a signed project to the data team | `POST /api/v1/projects/{pid}/handover` roles include `owner` and `sponsor` (`p2.permissions.yaml`); the ownership check in `p2_assign._write` lets the project's owner (raiser), the sponsor who signed the intent (set on the project record when the intent is signed) and a company admin through. Raj (approver) and others stay refused. Both were already in place in the tree when this card started; FIXE1 pins them with tests. |
| Owner gets 403 on her own intent's benchmark sheet | `g3.permissions.yaml`: `owner` added to the two GET rows only (sheet, doc). Writing and signing stay closed to her. The project access gate (`g1_access.http_gate`) still decides which intents she may open. |
| Trade check only runnable by the company admin; the 403 names Anita and Leo | `e3b_routes._may_run`: `analyst` and `head_of_data` pass (the Data team group is read-only on portfolios, which blocked them). Everyone else keeps the portfolio-access test. `e3b.permissions.yaml`: `head_of_data` added. |
| Check runs logged as PRODUCTION by "system" | `e3_recon.run_detail(..., who=None)` passes `who` to `run_log.record`; the route passes the signed-in person's name. Seeds, the shadow run and `run()` pass nothing and stay "system". Mode is unchanged. |
| `/centre/intent/{iid}/charter` "could not find that" for the sponsor | `CharterView.tsx`: a 404 moves to `/centre/intent/{iid}/sign` (an intent of work has no charter). No server link emitted for an intent of work pointed at /charter; the 2.0 initiative links keep working. |

## Permission rows changed

1. `p2.permissions.yaml` `POST /api/v1/projects/{pid}/handover`: roles `[company_admin, sponsor, analyst, owner]` (already so; unchanged by this card).
2. `g3.permissions.yaml` `GET /api/v1/build/{iid}/benchmarks/sheet`: `+ owner`.
3. `g3.permissions.yaml` `GET /api/v1/build/{iid}/benchmarks/sheet/doc`: `+ owner`.
4. `e3b.permissions.yaml` `POST /api/v1/recon/{code}/run`: `+ head_of_data` (now `company_admin, analyst, head_of_data, owner`).

## Test change

`tests/v1/test_e3b.py::test_uc2_02_...` asserted that an analyst on read-only portfolios cannot run a check. That is the behaviour the finding calls a bug; it now asserts the data team can, and an owner on read-only portfolios cannot.

## Tests

`pytest tests/v1/test_fixe1_rights.py` (Mei and Daniel hand over, Raj cannot; owner reads the sheet but cannot write or sign; Anita and Leo run the check, Sofia cannot; run log shows the person), plus `tests/v1/test_e3b.py test_e3a.py test_p2_assign.py test_p2.py test_role1.py test_g3g4.py tests/auth`. UI: `npx vitest run src/intents/CharterView.test.tsx`.
Backups: `D:/Temp/bak-fixe1/`.

## Not done

Mode stays PRODUCTION for manual check runs (not asked). The 400 "due date has already passed" on a hand-over is the real clock (M6), untouched.
