# Access control policy

Status: draft for the SOC 2 / ISO 27001 readiness work (W7). Owner: Nitin Bajpai. Review: every 6 months.

**Principle.** Least privilege, default deny, one company's data never visible to another.

## What exists in the product
- **Default deny.** Every route must be declared in `sh_platform/route_permissions.yaml` (or a `sh_platform/v1/*.permissions.yaml` card file) with the roles that may use it. A route that is not declared is refused (`sh_platform/auth/__init__.py`).
- **Roles.** `super_admin` (no company), `company_admin`, `sponsor`, `analyst`, `owner`, `approver`, `participant`, plus `head_of_data`. A refused person is told which role can act.
- **Company isolation.** Each company has its own data plane folder; a path that leaves it is refused (`sh_platform/plane.py`).
- **Sign-in.** Passwords hashed with scrypt; five wrong tries lock a login name for 60 seconds; sessions end after 30 minutes idle or 8 hours; cookies are HttpOnly, SameSite=Lax, Secure outside dev; state-changing calls need a CSRF token; WebSocket handshakes from another origin are refused.
- **MFA.** TOTP authenticator app plus one-time recovery codes (`sh_platform/auth/mfa.py`). Each office can switch on "MFA required" under Build > Audit log; sign-in then refuses anyone who has not set it up. Off by default (the public demo).
- **Audit.** Sign-ins, failed sign-ins, reads, exports, changes, settings and signed decisions are logged (see `soc2-iso27001-control-map.md`).

## Rules for people
1. Accounts are named, one per person; no shared logins.
2. New access is granted by a company administrator and removed (account disabled) the day a person leaves.
3. Company administrators and the platform super admin use MFA once their office has it switched on; the super admin account uses it from first use in any real deployment.
4. The platform super admin area is off in public deployments unless `SH_ENABLE_SUPERADMIN=1`.
5. Access is reviewed every quarter: list accounts per company, disable the ones not needed.

## Open
- Single sign-on (SAML/OIDC) is not built.
- No admin reset of a person's MFA (today: edit the account record by hand).
- No automatic quarterly access review report.
