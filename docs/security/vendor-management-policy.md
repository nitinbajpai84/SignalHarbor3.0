# Vendor management policy

Status: draft (W7). Owner: Nitin Bajpai. Review the list every 6 months.

**Rule.** Before a vendor receives any client data it is on this list with its purpose, what data it sees, where it processes it, and a reviewed security report or terms.

| Vendor | Purpose | Client data seen | Notes |
|---|---|---|---|
| Railway | Hosting, data volume | All, at rest | Region and encryption at rest to be confirmed in writing |
| OpenRouter, Google Gemini, Anthropic | Language models | Only text that passes the egress vault (real names are blocked) | Check each provider's no-training and retention terms; see `sh_platform/egress/` |
| GitHub | Source code, scans | None (code only) | Secret scanning on |
| Data connectors (banks, custodians) | Client data feeds | Per client authorisation | Only after a signed letter of authorisation |

## Rules
1. New vendor: the owner fills in a row, reads the vendor's SOC 2 / ISO 27001 report or security page, and records the decision.
2. Client data goes to a vendor only if the client's contract allows it.
3. A vendor with a breach or lost certification is reviewed within 5 working days.

## Open
- Vendor security reports are not yet collected or filed; the table is a starting list.
