# NM1: no model credit (North, speed, messages)

Nitin tested with both providers refusing for credit: North answered "I could not reach the model just now, so I have changed nothing" after 12 to 30 s, and the voice button said nothing useful.

## What changed
- `sh_platform/v1/i6_chat.py`: when the model was on and could not be reached (run status `error`), North answers by the rules path (same as model off): the intent and project exist, title and goal line come from the words (`opening`), the next template question is asked, a later turn fills the section asked about. The reply starts with one line (see Messages). "Changed nothing" stays only for the cases where nothing could be recorded (switched off for the company, unreadable or unfinished answer).
- `sh_platform/v1/router.py`: one refusal for credit or key ends the walk for that provider. A provider that refused in this call, or whose gateway breaker is open (`egress.gateway.provider_down`, new, read-only), is skipped before any client is built, tokenised or sent; its other tiers and alternates are skipped too. The company-name registration moved from `route()` to just before the first call that can leave, so a walk where everything refuses never pays for it.
- `sh_platform/v1/e6_trace.py`: `model_offline_line(plane, viewer)`, built on the wave-2 `model_trouble`.
- `sh_platform/v1/v1_voice_routes.py` and `ui/src/v1/voice/index.tsx`: when voice is unavailable or a transcribe or speak call fails, the note carries the same line; the screen shows it (beside the disabled microphone, and under the read-aloud button).

## Messages
- company_admin: "The model account is out of credit (provider). Top it up to get model answers and voice; until then answers come from rules." (other trouble codes: "Check the model settings in Settings ...").
- everyone else: "The assistant is offline for now; keep typing, your words are kept."

## Timing (POST /api/v1/intents/chat, every provider call answered 402; `.sh-tmp/nm1_profile.py`, TestClient on the nm1 env)
Where the time went (profile, slow-disk state): 8.4 s of 18.9 s was `io.open` (9 ms each on this box). The gateway tokenised the whole context (about 60 strings, each reading the name vault under a lock file, 2.7 s per call) for every tier tried, even with the breaker open; `register_company_names` ran in `route()` (about 1 to 8 s); the catalogue parse (2.4 s) is a once-per-process cost.

| Case | Before | After |
|---|---|---|
| process cold, first refusal per provider (2 provider calls) | 11.8 to 19.0 s | 3.6 to 4.8 s |
| process warm, breaker window reopened (2 provider calls) | 4.2 s (fast disk), not measured on slow disk | 2.0 to 2.3 s |
| process warm, breaker open (0 provider calls, the state Nitin was in) | 13.5 s (slow disk), 3.6 s (fast disk, same run) | 0.3 to 0.6 s |

On the real test server (port 8698, real providers, no credit): first request after start 6.5 to 11.4 s (cold process, real calls), then 0.6 to 1.6 s. Remaining warm time is intent and project creation, memory context reads and the view.

## Tests
`tests/v1/test_nm1.py` (stub provider refusing for credit): rules start and later turn, admin and other wording, one call per provider and zero with the breaker open, voice line. Three older tests that pinned "changed nothing" for a down model now pin the rules reply (`test_ni1`, `test_north_aq1`, `test_north_w2`). Run: test_nm1, test_i6a, test_north_loop, test_router, tests/egress: 295 passed (test_router and the others that copy `data/neera` need the copy to skip the locked `evidence.duckdb`: `.sh-tmp/nm1_pytest.py`).
