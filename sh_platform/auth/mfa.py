"""W7 MFA: TOTP (RFC 6238, SHA-1, 6 digits, 30 s) and one-time recovery codes. Stdlib only (pyotp is not installed).

An account's `mfa` field: {secret, enabled, recovery: [sha256 hex], last_counter}. The secret is shown once (start), switched on by the
first valid code (confirm), and recovery codes are shown once and kept only as hashes. The office setting "MFA required" lives in the
company plane (`ops/security.json`); off by default so the demo sign-in is unchanged.
ponytail: the secret sits in accounts.json in the clear (same file as the password hashes); encrypt with the backup key if a host needs it.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

STEP, DIGITS, WINDOW = 30, 6, 1
ISSUER = "Signal Harbor"


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def totp(secret: str, at: float | None = None, counter: int | None = None) -> str:
    n = int((time.time() if at is None else at) // STEP) if counter is None else counter
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    d = hmac.new(key, struct.pack(">Q", n), hashlib.sha1).digest()
    o = d[-1] & 15
    return str((struct.unpack(">I", d[o:o + 4])[0] & 0x7FFFFFFF) % 10**DIGITS).zfill(DIGITS)


def check_totp(secret: str, code: str, after_counter: int = -1, at: float | None = None) -> int | None:
    """The counter the code matched (so it can be refused if replayed), else None. Allows one step of clock drift."""
    code = "".join(str(code).split())
    if not (code.isdigit() and len(code) == DIGITS):
        return None
    now = int((time.time() if at is None else at) // STEP)
    for n in range(now - WINDOW, now + WINDOW + 1):
        if n > after_counter and hmac.compare_digest(totp(secret, counter=n), code):
            return n
    return None


def otpauth_uri(secret: str, email: str) -> str:
    return f"otpauth://totp/{quote(ISSUER)}:{quote(email)}?secret={secret}&issuer={quote(ISSUER)}&digits={DIGITS}&period={STEP}"


def _h(code: str) -> str:
    return hashlib.sha256(code.strip().lower().replace("-", "").encode()).hexdigest()


def new_recovery_codes(n: int = 8) -> tuple[list[str], list[str]]:
    """(codes to show once, hashes to keep)."""
    codes = [f"{secrets.token_hex(3)}-{secrets.token_hex(3)}" for _ in range(n)]
    return codes, [_h(c) for c in codes]


def use_recovery(mfa: dict, code: str) -> list[str] | None:
    """The hashes left after spending this code, or None if it is not one."""
    h = _h(code)
    left = [x for x in mfa.get("recovery", []) if not hmac.compare_digest(x, h)]
    return left if len(left) < len(mfa.get("recovery", [])) else None


def office_requires(app, company_id: str | None) -> bool:
    if not company_id:
        return False
    from sh_platform.jsonfile import read_json_strict
    from sh_platform.plane import PlaneStore
    try:
        f = PlaneStore(app.state.settings.data_root).plane_for(company_id).path("ops", "security.json")
        return bool((read_json_strict(f, dict) or {}).get("mfa_required"))
    except (LookupError, OSError, ValueError, PermissionError):
        return False


def set_office_requires(plane, required: bool) -> None:
    from sh_platform.jsonfile import write_json_atomic
    f = plane.path("ops", "security.json")
    f.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(f, {"mfa_required": bool(required)})
