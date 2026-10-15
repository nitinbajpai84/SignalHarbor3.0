# CB1 - provider outage breaker

Problem: with the model accounts out of credit, each agent call waited for transport retries and router fallbacks (changes endpoint 63 s).

Change (sh_platform/egress/gateway.py, `make_httpx_transport`, model transport only):
- `billing_code(status, body)`: 402 -> no_credit; 401/403 -> provider_key_refused; 429 whose body speaks of credit/billing/quota/limit (and not "per minute"/"retry"/"rate limit") -> no_credit. Only the code is kept, never the body.
- Such a refusal raises `EgressBlocked(code)` at once (not transient, so no retry) and opens a per-host in-process breaker for 300 s.
- While open, `send` raises the same code without touching the provider. After the window one trial call goes through (window re-arms; success closes it).
- Plain 429 and 5xx keep today's retry/backoff.
- The breaker sits inside the transport, after the gateway's masking, raw-rows, allowlist and log-before-send checks; the gateway still logs `sent` then `failed <code>` for every call, including breaker refusals.
- Router: no edit needed. The codes are already in `PROVIDER_FAILED`, so the router falls back to rules and the wave-2 `model_trouble` note as before; the calls it walks through (alt, next tier) now return instantly. `retry_up` only follows an unusable reply, never a refusal.

Tests: tests/egress/test_outage_breaker.py (402/401/403 under 2 s, no retry; window skip; one trial; 429 still retried; credit-429 opens; egress log lines). tests/egress/test_model_retry.py: 401 now surfaces as EgressBlocked, and the fixture clears the breaker.
Backups: .sh-tmp/*.bak-cb1.
Ceiling: breaker is per process; concurrent callers may all trial once after the window.

## Review (security, 10 Oct)

- **Verdict:** pass, after one fix.
- **Order of checks:** the breaker runs inside the model transport. It only sees a call after host, allowlist, masking, raw-row and URL checks and after the `sent` log line. A refusal is logged as `failed <code>`. Nothing is skipped or reordered.
- **Secrets:** only the refusal code is kept. The 429 body is read for word matching and is never logged or stored. The key is unchanged and is still read by name and attached only for the provider host.
- **Routing:** the breaker can only refuse a call. It never redirects one. A fallback to another provider goes through the full gateway again. The internet transport and the speech transport (`tries=1`) never touch the breaker.
- **Threads:** single dict operations under the GIL are safe. The read-then-rearm race allows several trial calls at most, as already noted.
- **Fix:** the 429 classification called `resp.read()` with no size cap, which bypassed `MAX_RESPONSE_BYTES`. It now reads at most about 2000 bytes. Backup: `.sh-tmp/gateway.py.bak-cb1-review`.
- **Tests:** `tests/egress` plus `tests/v1/test_router.py` passed, 276 tests.
- **Follow-up (not a security issue):**
  - OpenRouter also returns 403 when moderation flags a prompt. Under the 403 rule in this card, one flagged prompt opens the breaker for every OpenRouter call for 5 minutes.
  - The breaker is keyed by host, so two keys on the same host share one breaker.
