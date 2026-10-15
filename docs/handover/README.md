# Signal Harbor handover pack

Start here. Four documents:

| File | For | What it covers |
|---|---|---|
| [TECHNICAL-GUIDE.md](TECHNICAL-GUIDE.md) | Engineers | Architecture, code layout, data, agents, running, deploying, tests, conventions, maintenance |
| [USER-AND-TESTING-GUIDE.md](USER-AND-TESTING-GUIDE.md) | Testers, product owners | Every feature by centre, who can use it, how to test it, what we tested and the results, a regression checklist |
| [ACCESS-AND-ACCOUNTS.md](ACCESS-AND-ACCOUNTS.md) | Everyone | Repository, hosted demo, demo sign-ins (no passwords), accounts to create, variables to set |
| [`../../.env.example`](../../.env.example) | Engineers | Every setting the code reads, with empty values to fill in |

Architecture diagrams: `docs/architecture/` (open the `.html` files in a browser). Start with `sh-three-planes-security.html`.

## How to get started (new team)

1. Accept the GitHub invitation to the private repository.
2. Clone it, copy `.env.example` to `.env` and fill in your own keys (the access sheet says which are required).
3. Follow "Running locally" in the technical guide.
4. Sign in with the demo accounts and walk the regression checklist in the user and testing guide.
5. For hosting, create your own Railway project (or any container host) and set the same variables there.

## Sharing rules

- No passwords or API keys are in this repository or its history (checked on 13 Oct 2026). Keep it that way: keys live only in `.env` (ignored by git) or in the host's variables.
- Passwords for the demo accounts are shared separately, never in a document or a commit.
- Every team uses its own AI model, speech and market data keys.
