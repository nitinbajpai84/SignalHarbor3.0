# Feeds setup: the four sandbox API connectors

Nitin creates each developer account and sets the variables himself (user environment, then restart the backend). Nothing here is ever typed into chat, logged or stored by the product. The connector reads each name when it runs and reports only the **names** still missing.

Every call goes through the egress gateway. Per company, turn on the **feeds** switch and list the provider host (`sh_platform.v1.connectors._http.enable(plane, host)` does both; the Connections page calls it). Until then a fetch is refused and logged as blocked.

Each connector writes into the dropbox, so the pack reads the files like any file a person drops. Plaid, GoCardless and the Singapore bank write **camt.053**; Saxo writes the **custodian positions** and **custodian transactions** CSVs.

| Provider | Create | Variables | Egress host |
|---|---|---|---|
| Plaid (sandbox) | Free developer account at dashboard.plaid.com; use the Sandbox keys | `PLAID_CLIENT_ID`, `PLAID_SECRET` (the sandbox secret) | `sandbox.plaid.com` |
| Saxo OpenAPI (simulation) | Free developer account at developer.saxo; log in, open the simulation app and generate a 24-hour token | `SAXO_TOKEN` (renew daily; `SAXO_APP_KEY` is not needed for a token) | `gateway.saxobank.com` |
| GoCardless Bank Account Data | Free account at bankaccountdata.gocardless.com, User secrets: create a secret. Then link the sandbox bank once (institution `SANDBOXFINANCE_SFIN0000`: create an agreement and a requisition, open the link, accept) | `GOCARDLESS_SECRET_ID`, `GOCARDLESS_SECRET_KEY`, `GOCARDLESS_REQUISITION_ID` (the id of the linked requisition; not secret) | `bankaccountdata.gocardless.com` |
| Singapore bank sandbox (DBS developer portal or OCBC) | Register on the bank's developer portal; confirm the terms allow sandbox use, create an app with client credentials | `BANKSG_HOST` (sandbox host, bare name), `BANKSG_CLIENT_ID`, `BANKSG_CLIENT_SECRET` | the value of `BANKSG_HOST` |

Notes
- Plaid builds its own test Item in the sandbox, so no bank login is needed.
- The Singapore connector follows a common open-API shape (`/oauth/token`, `/v1/accounts`, `/v1/accounts/{id}/transactions`). DBS's public portal documents very little without a partner agreement, so check these paths against the portal once the account exists and adjust `banksg.py` if they differ.
- Saxo's trade fields come from `cs/v1/audit/orderactivities`; check them on the first live run.
- The camt.053 files need the camt.053 reader of the file-format branch (g-feeds-files) in the pack; the Saxo CSVs are read today.
- If a provider's terms do not fit, Alpaca (paper trading) is the free substitute named in the gap plan.
