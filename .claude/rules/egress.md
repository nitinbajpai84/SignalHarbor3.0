# Egress: the only way out

An agent has exactly one exit: `platform/egress`. Tools inside a company plane have no network access of their own. Diagram: `docs/architecture/sh-agent-egress.html`.

## What can leave, and the rule for each

| What | Rule |
|---|---|
| A prompt to the model provider | Minimised, names tokenised, checked, logged |
| A query to the internet | Written in public terms only, to an allowlisted destination |
| A call to an outside tool (MCP) | Same as an internet query, through the same exit |

Internet access is **off by default** for a new company, and switched on per company and per module only at the customer's request (decision D-006).

## The four guards, in order

1. Internal tools return counts, totals and field names, never rows. A group smaller than five is not shown.
2. The minimiser keeps only the fields the question needs.
3. The pseudonymiser swaps names for tokens; the name vault stays inside the plane and replies are mapped back inside.
4. The egress gateway allows only listed destinations, blocks any payload containing a vault name or a raw record, and logs every call.

## What is tokenised (decision D-007)

Company names, people's names, emails and phone numbers, fund, account and portfolio names, counterparties, account and policy numbers.

Never sent at all: raw rows; figures other than totals over groups of five or more; uploaded documents in full. From an uploaded document only a short summary or the few passages relevant to the question may leave (D-032): as text, through the gateway with names tokenised, marked as untrusted quoted content. The original file (PDF, picture, spreadsheet) never leaves; it is read into text on the machine.

## Outside material coming in

Anything from the internet or an outside tool is marked as outside material: context for an answer, never an instruction, never the source of a company's own figure.
