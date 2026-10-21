# SOC 2 / ISO 27001 control map

Status: draft (W7), 21 Oct 2026. "Done" means it exists in code or a document in this repository and has a test or a written procedure. It does not mean audited. Anything marked Open is not done.

| Need | SOC 2 (Trust Services) | ISO 27001:2022 Annex A | State | Where |
|---|---|---|---|---|
| Role-based, default-deny access | CC6.1, CC6.3 | A.5.15, A.5.18, A.8.3 | Done | `sh_platform/auth/__init__.py`, `route_permissions.yaml`, `v1/*.permissions.yaml`; tests `tests/auth/` |
| Company data isolation | CC6.1 | A.8.3, A.8.22 | Done | `sh_platform/plane.py` |
| Password storage, lockout, session limits, CSRF | CC6.1, CC6.6 | A.5.17, A.8.5 | Done | `auth/accounts.py`, `auth/sessions.py` |
| Multi-factor authentication | CC6.1 | A.8.5 | Done (TOTP, recovery codes, office "MFA required"); off by default for the demo | `auth/mfa.py`, `auth/routes.py`; `tests/v1/test_g_security.py` |
| Single sign-on | CC6.1 | A.5.16 | Open | none |
| Admin reset of a person's MFA | CC6.2 | A.5.16 | Open | none |
| Audit log of sign-ins, reads, exports, changes, settings, signed decisions | CC7.2, CC7.3 | A.8.15, A.8.16 | Done | `v1/v3_audit.py`, hook in `auth/__init__.py`, page Build > Audit log (`ui/src/v3/build/AuditPage.tsx`) |
| Tamper evidence for the log | CC7.2 | A.8.15 | Done (hash chain, `verify`); cutting lines off the end is only caught by keeping the exported head hash | `v1/v3_audit.py` |
| Audit export for auditors | CC7.2 | A.8.15 | Done (CSV with chain head) | `GET /api/v3/audit/export.csv` |
| Repeated reads collapsed in the log (one per person and path per minute) | CC7.2 | A.8.15 | Known limit | `v3_audit.record_request` |
| Log shipping off the host, alerting on odd events | CC7.2 | A.8.16 | Open | none |
| Encrypted, timestamped backups | A1.2 | A.8.13 | Done | `tools/backup.py` |
| Tested restore | A1.3 | A.8.13, A.5.30 | Done (tool); monthly run is a procedure | `tools/restore_test.py`, `backup-and-restore-policy.md` |
| Scheduled backups, off-site copy | A1.2 | A.8.13 | Open | none |
| Encryption of data at rest on the volume | CC6.1, C1.1 | A.8.24 | Open (host level; to confirm with Railway) | none |
| Encryption in transit | CC6.7 | A.8.24 | Host (HTTPS at Railway); cookies Secure outside dev | `auth/routes.py` |
| Singapore region option | C1.1 | A.5.23 | Open | hosting setting |
| Names kept from models | C1.1 | A.5.34, A.8.12 | Done | `sh_platform/egress/` |
| Dependency vulnerability scan | CC7.1 | A.8.8 | Done as config; not yet run on GitHub | `.github/workflows/security-scan.yml` |
| Secret scan | CC6.1, CC7.1 | A.8.4, A.8.28 | Done as config; not yet run on GitHub | `.github/workflows/security-scan.yml` |
| Penetration test by an independent party | CC4.1, CC7.1 | A.8.8, A.8.29 | Open | none |
| Access control policy | CC5.3, CC6.1 | A.5.15, A.5.1 | Done (draft) | `access-control-policy.md` |
| Incident response plan | CC7.3, CC7.4, CC7.5 | A.5.24 to A.5.27 | Done (draft); no tabletop run yet | `incident-response-plan.md` |
| Backup and restore policy | A1.2, A1.3 | A.8.13 | Done (draft) | `backup-and-restore-policy.md` |
| Change management | CC8.1 | A.8.32 | Done (draft); branch protection Open | `change-management-policy.md` |
| Vendor management | CC9.2 | A.5.19 to A.5.22 | Done (draft); vendor reports not collected | `vendor-management-policy.md` |
| Data retention and classification | C1.1, C1.2 | A.5.12, A.5.13, A.8.10 | Done (draft); deletion manual | `data-retention-and-classification-policy.md` |
| Acceptable use | CC1.4, CC2.2 | A.5.10, A.6.3 | Done (draft); no signed acknowledgement | `acceptable-use-policy.md` |
| Risk assessment and register | CC3.1 to CC3.4 | 6.1.2, 8.2 | Open | none |
| ISMS scope, statement of applicability, internal audit, management review | CC1.x, CC4.x | 4.x to 10.x | Open | none |
| Security awareness training, background checks | CC1.4 | A.6.1, A.6.3 | Open | none |
| Business continuity and disaster recovery plan beyond backups | A1.2 | A.5.29, A.5.30 | Open | none |
| Compliance platform (evidence collection) and auditor | all | all | Open (Nitin decides) | `docs/v3/PROGRAM-GAPS.md` W7 |
