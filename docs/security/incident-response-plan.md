# Incident response plan

Status: draft (W7). Owner: Nitin Bajpai. Test: one tabletop exercise a year.

**What counts.** Unauthorised access, data leaving to the wrong place, a lost key or laptop, a malicious dependency, an outage affecting a client, or a wrong figure that went out as verified.

## Steps
1. **Detect.** Sources today: the audit log (failed sign-ins, odd exports), `/api/health`, Railway deploy and service logs, a user report. No automatic alerting yet.
2. **Triage (within 1 hour).** Open a record: date, who found it, what is affected, which companies. Severity: S1 client data exposed or service down; S2 a control failed but nothing exposed; S3 near miss.
3. **Contain.** Disable the account (`disabled` on the account record), rotate `SH_SESSION_SECRET` (signs everyone out), rotate model and connector keys, take the service down if exposure is ongoing.
4. **Preserve evidence.** Export the audit log (CSV with chain head) and check the chain before changing anything; keep deploy logs.
5. **Recover.** Fix the cause; restore from the last good encrypted backup if data was damaged (`backup-and-restore-policy.md`); confirm with `tools/restore_test.py`.
6. **Notify.** Affected clients within 72 hours of confirming personal data was exposed (PDPA Singapore; GDPR where it applies), sooner if a contract says so. Nitin decides and signs the message.
7. **Learn.** Within 5 working days: a short write-up (what happened, why, what changes), actions tracked to done.

## Open
- No on-call rota or paging; no log shipping off the host; no named backup responder.
