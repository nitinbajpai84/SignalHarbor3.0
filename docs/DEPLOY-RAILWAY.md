# Deploy the Signal Harbor demo to Railway

One service, one volume. Anyone with the link can sign in and try the Evergreen family-office demo. All data is synthetic.

## Before you start
- Repo folder: `<repo>` (the folder with `Dockerfile` and `railway.json`).
- Keys you will paste yourself (never into a file, chat or the repo): `OPENROUTER_API_KEY` (required for the agents), `OPENAI_API_KEY` and `GOOGLE_API_KEY` (optional).

## Steps
```
npm i -g @railway/cli
railway login
railway init                                  # name it signal-harbor-demo
railway volume add --mount-path /data         # the demo data lives here and survives redeploys
railway variables --set SH_SESSION_SECRET="<a random 48+ character value>"
railway variables --set OPENROUTER_API_KEY="<your key>"
railway variables --set SH_DAILY_MODEL_CAP_USD=2
railway variables --set SH_DEMO_PASSWORD="<one shared demo password, 12+ characters>"   # optional, see Logins
railway up                                    # builds the Dockerfile and deploys
railway domain                                # prints the public link
```
Generate the session secret in PowerShell: `-join ((48..57)+(65..90)+(97..122) | Get-Random -Count 56 | % {[char]$_})`.
Optional: `railway variables --set OPENAI_API_KEY="..."` and `--set GOOGLE_API_KEY="..."`.

First deploy takes about 5 to 8 minutes (UI build, Python packages). The first boot then seeds the demo into `/data` (about 30 seconds); the health check waits up to 5 minutes. Later boots find the volume seeded and touch nothing.

## Logins
- Easiest: set `SH_DEMO_PASSWORD` (12+ characters). Every seeded account then signs in with it. Emails are `<name>.evergreen@example.test`; the 8 accounts and their roles are in the file below (the email and role columns; ignore the password column).
- Otherwise each account has its own generated password in `/data/_control/seed_credentials.txt`. Read it yourself: `railway ssh` then `cat /data/_control/seed_credentials.txt`. It is never written to the logs.
- Share the link, the email and the password with the people you invite. There is no sign-up page.

## What is switched on for a public link
| Setting | Public demo value |
|---|---|
| `SH_MODE` | `prod` (set in the image): secure cookies, strong session secret required |
| Model mode | Testing (cheap OpenRouter models: qwen3.7-flash, gpt-oss-120b); "Real use" is refused unless `SH_ALLOW_REAL_MODE=1` |
| `SH_DAILY_MODEL_CAP_USD` | 2 per company per UTC day (from the cost log). After it, the agents answer from rules with a plain note until tomorrow. `0` turns the cap off |
| `SH_CHAT_TURNS_PER_HOUR` | 30 agent chat turns per account per hour (answer 429 after). `0` turns it off |
| Super-admin routes | Off. No super-admin account is seeded either. `SH_ENABLE_SUPERADMIN=1` opens them |
| Voice | Off: speech only runs in dev mode |
| Model provider | `SH_MODEL_PROVIDER=openrouter` (set in the image; the agents are off without it) |
| Scheduler | On (`SH_SCHEDULER=on`) |

Worst case model spend is about the cap times the number of companies per day (one demo company: 2 USD a day). Watch your OpenRouter dashboard too, and set a credit limit on the key there.

## Reset the demo
The seed never wipes. To start again: `railway ssh`, then `rm -rf /data/evergreen /data/_control` and `exit`, then `railway redeploy`. The next boot seeds a fresh demo with new generated passwords. (If `SH_DEMO_PASSWORD` is set it is applied again.)

## Costs
Railway Hobby plan: about 5 USD a month, which includes 5 USD of usage; the service and a small volume usually fit in it, with the rest billed by use. Models are billed by OpenRouter separately (capped as above). Remove everything with `railway down` or delete the project in the dashboard.

## Do not
- Never load real client or family-office data. This is a public link; the data is synthetic by design.
- Never put a key, password or the credentials file in the repo, a chat, a screenshot or the Dockerfile. Set them with `railway variables --set` only.
- Never share the link and the shared password in the same public place.
- Do not set `SH_ENABLE_SUPERADMIN=1` or `SH_ALLOW_REAL_MODE=1` on a link others can open.
- Do not scale to more than one replica: the rate limit and the SQLite/DuckDB files assume one process.
