# Data retention and classification policy

Status: draft (W7). Owner: Nitin Bajpai.

## Classes
| Class | Examples | Handling |
|---|---|---|
| Restricted | Client financial data, holdings, statements, figures, names of people and accounts | Company plane only; names never go to a model (egress vault); encrypted in backups; access by role; reads and exports in the audit log |
| Confidential | Account records, password hashes, MFA secrets, audit log, session secret | Server only; never shown in the UI; never in the repository |
| Internal | Policies, specs, code | Repository |
| Public | Marketing pages, demo with synthetic data | Open |

Demo and test data is synthetic. Real client data is never used in tests or samples.

## Retention
- Client data: for the contract term, then deleted or returned within 30 days of the client's written request (delete the company plane folder and its backups).
- Audit log: kept at least 12 months; entries are append-only and are not deleted in that period.
- Backups: 30 daily and 12 monthly copies, then deleted.
- Accounts of people who leave: disabled at once, removed after 12 months.

## Open
- Deleting a company plane is a manual job, not a button; so is deleting that company's backups.
- No automatic expiry of old audit entries or backups.
- A Singapore region is a hosting setting to confirm with Railway; encryption at rest of the data volume is the host's, not ours.
