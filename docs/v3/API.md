# The public API

A read-only REST API for your own tools to read what Consume shows: the office's figures with their receipts, the signals that fired, the document list, and plain-language questions. It can never change anything.

Base: `https://<your harbor>/api/public/v1`. The schema is served at `/api/public/v1/openapi.json` (OpenAPI 3).

## Keys

An office admin makes keys under **Build, API keys**.

- A key belongs to one company. It looks like `shpub.<company>.<key id>.<secret>` and is shown **once**; Harbor keeps only a hash of the secret. Lost? Revoke it and make another.
- **Scopes**: `figures`, `ask`, `signals`, `documents`. A call outside the key's scopes is refused with 403.
- **Entities (optional)**: a key can be limited to some entity codes. It then sees only items tagged with one of them; an item with no entity tag is withheld. A key limited this way cannot `ask`, because an answer is worked out over the whole office.
- **Family-member keys** are limited to the member's own share. Leave the entities empty and Harbor fills them from the member's signed `family_access_<member>_<entity>` rules (full or summary); if the office has none, list the entities by hand. A family key cannot `ask`.
- **Rate limit**: 60 calls a minute per key by default (1 to 600 when made). Over it, you get 429 and `Retry-After: 60`.
- **Every call is logged** in your own company space (key id, route, time, status). The page shows the latest.
- A key opens only its own company. A key shown another company's name is refused.

Send the key as a bearer token:

```
export H=https://harbor.example.test
export K=shpub.evergreen.3fa9c1d2e4b6.xxxxxxxxxxxxxxxxxxxxxxxx
```

## Figures

```
curl -s -H "Authorization: Bearer $K" $H/api/public/v1/figures
```

```json
{"figures": [{"id": "fig-cash-break", "name": "Cash break", "definition": "Cash the bank shows less cash the books show",
              "grain": ["entity"], "version": 2, "status": "verified", "last_run_at": "2026-10-20T06:00:12Z", "held": false}]}
```

`held` is true when a newer version failed its tie-out and the last verified one stays current.

One figure, with its receipts:

```
curl -s -H "Authorization: Bearer $K" $H/api/public/v1/figures/fig-cash-break
```

`receipts` holds what the figure reads (`reads`), a fingerprint of the query (`sql_hash`), the tie-out that checked it, what it assumed, and its runs. `lineage` gives files, then tables, then the figure.

## Ask

```
curl -s -H "Authorization: Bearer $K" -H "Content-Type: application/json" \
     -d '{"text": "How much cash do we hold in Singapore dollars?"}' $H/api/public/v1/ask
```

```json
{"answer": "The office holds SGD 1,600,000 in cash.", "figure": {"id": "fig-cash-by-currency", "name": "Cash by currency", "v": 2},
 "trace": [{"kind": "tool", "label": "Read cash by entity"}, {"kind": "guard", "label": "Checked every number against the data"}],
 "used": [], "cached": false, "ms": 840, "as_of": "2026-10-20"}
```

This is the same answer path as the Consume page: the office's verified figures first, then Lumen with the number guard. A key asks as the least a person can be (a participant), and its answers are kept per question and data version, as on the page. Questions are up to 2000 characters.

## Signals

```
curl -s -H "Authorization: Bearer $K" "$H/api/public/v1/signals?status=open"
```

`status` is optional (`open`, `acted`, `dismissed`). Newest first. Each signal has its title, subject, severity, the role it was routed to, the message and its evidence (the receipts). The person it went to and the raw event are not included.

## Documents

```
curl -s -H "Authorization: Bearer $K" $H/api/public/v1/documents
```

Metadata only: title, type, file name, the fund it is matched to, valuation and received dates, whether it is current. **No file bytes and no storage path, ever.**

## Errors

All errors are `{"detail": {"error": "...", "message": "..."}}`.

| Status | error | Meaning |
|---|---|---|
| 401 | `unauthorized` | No key, a wrong or revoked key |
| 403 | `scope_not_granted` | The key does not have that scope (or cannot `ask`) |
| 404 | `not_found` | No such figure, or not one this key may see |
| 422 | | The body is not valid (for example an empty question) |
| 429 | `rate_limited` | Over the key's calls a minute; wait `Retry-After` seconds |

## Webhook: signal fired

For a key with the `signals` scope, an admin can register one https URL (Build, API keys, Add webhook). Harbor shows the signing secret **once**.

1. The URL's host must be on the company's **webhook list** (the same egress allow-list the delivery channels use). Until it is, nothing is sent and the page says so. Delivery goes through the egress gateway: https only, names tokenised, logged by host.
2. Harbor sends `POST` with a JSON body and these headers:
   - `X-Harbor-Event: signal.fired`
   - `X-Harbor-Signature: sha256=<hex>`, the HMAC-SHA256 of the **exact request body** using the signing secret.

```json
{"event": "signal.fired", "signal": {"id": "sg-4f2a9c01de", "signal": "uc01-call-arrives", "title": "A capital call arrives", "subject": "Call 7",
 "severity": "needs", "route_to": "decision_maker", "at": "2026-10-20T08:00:00Z", "message": "A call of USD 1,250,000 is due 23 October."}}
```

Check it on your side:

```python
import hmac, hashlib
def ok(secret: str, body: bytes, header: str) -> bool:
    want = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(want, header)
```

Names in the message arrive as tokens (the egress rule). A webhook failure never stops a signal; a key limited to some entities hears only signals tagged with them. Delivery is once, with no retry: fetch `/signals` to catch up.

## MCP: use Harbor from your own AI tool

`tools/mcp_harbor.py` is a small MCP server (stdio) over this API with three tools: `ask`, `figures` (the list, or one figure with receipts when given an `id`) and `signals`. It uses the standard library only.

```json
{"mcpServers": {"signal-harbor": {"command": "python", "args": ["tools/mcp_harbor.py"],
  "env": {"HARBOR_API_KEY": "shpub.evergreen.3fa9c1d2e4b6.xxxx", "HARBOR_API_BASE": "https://harbor.example.test"}}}}
```

The key limits what the tool can read, exactly as above. Whatever it reads goes to the AI tool you connect: connect only one you are content to see that key's data. (For a person's own assistant inside Harbor's rules, use the signed-in MCP in Settings instead.)

## Not in this version

No writes. No per-figure scopes (a key sees all figures, or only the entities it names). Rate limits are counted in memory on one server process. Webhooks are not retried.
