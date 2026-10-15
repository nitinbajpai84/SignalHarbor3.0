# Access and accounts

This sheet says where things are and which accounts the new team needs. It holds no secrets: no passwords, keys or tokens. Those live in `.env` (git-ignored) or in the host's variables, and the owner shares demo passwords separately.

## 1. Source code

| Item | Detail |
|---|---|
| Repository | https://github.com/nitinbajpai84/signalharborv2.0 |
| Visibility | Private |
| Access | The owner invites collaborators by GitHub username. Accept the invitation from GitHub before cloning. |
| Default branch | `main`. Pushes to `main` redeploy the hosted demo. |

## 2. Hosted demo

| Item | Detail |
|---|---|
| Address | https://signalharborv20-production.up.railway.app |
| Host | Railway, project `cooperative-communication`, service `signalharborv2.0` |
| Attached services | Postgres, Redis, and a `/data` volume (company data, accounts, seed credentials) |
| Deploys | Automatic on every push to `main` |
| Start-up | `tools/start.sh` seeds an empty volume on first boot, then starts the web app. Logins are written to `/data/_control/seed_credentials.txt` on the volume, never to the log. |

## 3. Demo sign-ins (Evergreen Office)

The demo company is Evergreen Office, a synthetic family office. All sign-in emails follow one pattern:

`<first>.<last>.evergreen@example.test`

| Person | Role in the demo | Sign-in email |
|---|---|---|
| Mei Chen | Operations lead, business owner | `mei.chen.evergreen@example.test` |
| Daniel Foo | Chief Investment Officer, sponsor | `daniel.foo.evergreen@example.test` |
| Raj Patel | Finance, approver | `raj.patel.evergreen@example.test` |
| Sofia Reyes | Risk, participant | `sofia.reyes.evergreen@example.test` |
| Anita Rao | Head of data (also analyst) | `anita.rao.evergreen@example.test` |
| Leo Park | Data engineer, analyst | `leo.park.evergreen@example.test` |
| Grace Ong | Company administrator | `grace.ong.evergreen@example.test` |

Passwords:

- **On the hosted demo:** one shared demo password, set by the `SH_DEMO_PASSWORD` variable on the host. The owner gives it to you separately.
- **Locally:** the seed writes a credentials file at `<SH_DATA_ROOT>/_control/seed_credentials.txt` (by default `data/_control/seed_credentials.txt`). It is git-ignored and must not be committed, copied into a document or pasted into a chat.

Source of the list: `tools/seed_evergreen.py` (`PEOPLE`, `email_of`).

## 4. Third-party accounts the new team creates in its own name

| Account | Needed for | Required? | Notes |
|---|---|---|---|
| Model provider: OpenRouter, or a direct provider key | All agent and model calls | Yes, one of them | OpenRouter is the hosted demo's provider. Paid per use. |
| Google AI key (Gemini) | Model calls (Gemini provider) and voice input | Optional | Free for development. Voice is off in production unless `SH_SPEECH_IN_PROD=1`. |
| FRED API key | Live economic data pull in the market views | Optional | Free. Without it the pull is skipped. |
| Finnhub API key | Live market news and index data | Optional | Free tier. Without it the pull is skipped. |
| Railway account (or another container host) | Hosting the web app, Postgres and Redis | Yes, for hosting | Create your own project. Local development needs no hosting account. |
| GitHub account | Access to the repository | Yes | Must be invited by the owner. |

Each team uses its own keys. Do not reuse the owner's keys.

## 5. Variables to set on the host

Names only. The full list with a one-line description of each is in `.env.example` at the repository root.

Set by the Dockerfile (no action needed): `SH_MODE=prod`, `SH_DATA_ROOT=/data`, `SH_SCHEDULER=on`, `SH_ROUTER=on`, `SH_MODEL_PROVIDER=openrouter`.

Set on the host by you:

| Variable | Required? | Purpose |
|---|---|---|
| `SH_SESSION_SECRET` | Yes | Signs login cookies. Random, 32+ characters. |
| `OPENROUTER_API_KEY` | Yes (or another model key) | Model calls. |
| `SH_DEMO_PASSWORD` | For the demo | Shared password for the demo accounts, 12+ characters. |
| `SH_PUBLIC_BASE_URL` | Recommended | Public address used in email links. |
| `DATABASE_URL` | Production mode | Postgres connection. Reference it from the Railway Postgres service. |
| `REDIS_URL` | Production mode | Redis connection. Reference it from the Railway Redis service. |
| `GOOGLE_API_KEY` | Optional | Gemini model and voice. |
| `SH_SPEECH_PROVIDER`, `SH_SPEECH_IN_PROD` | Optional | Voice input setting. |
| `FRED_API_KEY`, `FINNHUB_API_KEY` | Optional | Live market data pulls. |
| `SH_EGRESS_DEFAULT` | Leave at `off` | Internet access for companies stays off unless a customer asks. |

`RAILWAY_ENVIRONMENT` and `PORT` are set by Railway. The live Variables tab in Railway is the authority for what is currently set; this list was written from the code, not read from the live service.

## 6. Rules for this sheet

- Never write a password, key or token into this file, a commit or a ticket. Rotate any value that was exposed.
- Demo data is synthetic. Real client data does not go on the demo or into the repository.
