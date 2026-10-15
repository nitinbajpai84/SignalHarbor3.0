# E3a Rules register and Admin rules screen

**What changed.** `e3_rules` reads and writes `business_rules` and `rule_versions`. `current(plane, rule_code, on_date)` returns only signed versions in force that day ({rule_version_id, parameters, definition_text}). The rule's owner proposes a draft; a different person signs it. Past versions stay, so past runs keep the version id they recorded. New people get a `users` row on first use (owner and signer columns are user ids). Screen `/centre/admin/rules`: Rule, Value in words, From, Owner, State, history per rule, propose, approve.

**Files.** `sh_platform/v1/e3_rules.py`, `e3a_routes.py`, `e3a.permissions.yaml`, `ui/src/v1/e3a/{api.ts,AdminRules.tsx,routes.tsx,e3a.test.tsx}`, `tests/v1/test_e3a.py`.

**Routes.** `GET /api/v1/rules`, `GET /api/v1/rules/{code}/history`, `POST /api/v1/rules/{code}`, `POST /api/v1/rules/versions/{id}/approve`.

**Test on the demo.**
1. Sign in as an Operations analyst, open `/centre/admin/rules`, propose `cash_tolerance`: "Cash may differ by 5,000 USD per entity per day", from 1 Jan, values `{"abs_amount": 5000, "currency": "USD"}`, kind tolerance.
2. Open the rule's history: the version shows "Waiting for a signature" and no Approve you can use yourself (the server refuses).
3. Sign in as another analyst or the company admin, press Approve: state becomes Signed.
4. `e3_rules.current(plane, "cash_tolerance", date)` now returns it.

**Known limits.** Only the rule's owner proposes changes to it (ownership transfer is not built). No retire action yet (`current` ignores anything not approved). Approving a later version does not set `effective_to` on the earlier one; `current` takes the latest `effective_from` on or before the date. Same display name as the owner counts as the owner (fails closed). Roles allowed: company_admin, analyst, sponsor. No audit event row (no events table exists for rules).

**Wiring for the orchestrator.** Add `/centre/admin/rules` to the Admin links next to "Data model" (not done: shared nav). E0e's seed can create rules through `propose` then `approve` with two different viewers.
