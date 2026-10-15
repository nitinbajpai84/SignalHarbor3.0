"""Per-person MCP tokens: issued in Settings, scoped, revocable, stored hashed (sha256 of a 256-bit secret) in the company plane.

Token text: `shmcp.<company_id>.<token_id>.<secret>`. The secret is shown once, at issue. Verifying never reads another company's plane.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import PlaneStore, valid_company_id

SCOPES = ("read", "propose", "export")
MAX_PER_PERSON = 10
DEFAULT_DAYS = 30
MAX_DAYS = 365


class TokenError(ValueError):
    """Safe to show."""


def _path(plane):
    return plane.area("context") / "mcp_tokens.json"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def _rows(plane) -> list[dict]:
    return read_json_strict(_path(plane), list) or []


def issue(plane, account_id: str, label: str, scopes=("read",), days: int = DEFAULT_DAYS) -> dict:
    """Returns the public record plus `token` (the only time it is visible)."""
    label = " ".join(str(label or "").split())[:60]
    if not isinstance(scopes, (list, tuple)) or not all(isinstance(s, str) for s in scopes):
        raise TokenError("Scopes are read, propose and export.")
    scopes = sorted(set(scopes))
    if not label:
        raise TokenError("Give the token a name, such as the assistant it is for.")
    if not scopes or set(scopes) - set(SCOPES):
        raise TokenError("Scopes are read, propose and export.")
    if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= MAX_DAYS:
        raise TokenError(f"A token lasts 1 to {MAX_DAYS} days.")
    tid, secret = secrets.token_hex(6), secrets.token_urlsafe(32)
    rec = {"id": tid, "account_id": account_id, "label": label, "scopes": scopes, "hash": _hash(secret),
           "created": _now().isoformat(timespec="seconds"), "expires": (_now() + timedelta(days=days)).isoformat(timespec="seconds"),
           "revoked": False, "last_used": None}
    with lock_for(_path(plane)):
        rows = _rows(plane)
        if sum(1 for r in rows if r["account_id"] == account_id and _active(r)) >= MAX_PER_PERSON:
            raise TokenError("Revoke a token you no longer use first.")
        write_json_atomic(_path(plane), rows + [rec])
    return {**public(rec), "token": f"shmcp.{plane.company_id}.{tid}.{secret}"}


def _active(r: dict) -> bool:
    return not r["revoked"] and datetime.fromisoformat(r["expires"]) > _now()


def public(r: dict) -> dict:
    return {k: r[k] for k in ("id", "label", "scopes", "created", "expires", "revoked", "last_used")} | {"active": _active(r)}


def listing(plane, account_id: str) -> list[dict]:
    return [public(r) for r in _rows(plane) if r["account_id"] == account_id]


def revoke(plane, token_id: str, account_id: str, admin: bool = False) -> bool:
    """A person revokes their own tokens; a company admin may revoke anyone's of the company."""
    with lock_for(_path(plane)):
        rows = _rows(plane)
        hit = [r for r in rows if r["id"] == token_id and (admin or r["account_id"] == account_id)]
        for r in hit:
            r["revoked"] = True
        if hit:
            write_json_atomic(_path(plane), rows)
    return bool(hit)


def verify(data_root, text: str):
    """(plane, record) for a live token, else None. Every failure looks the same."""
    try:
        prefix, company, tid, secret = str(text or "").split(".", 3)
        if prefix != "shmcp" or len(text) > 200:
            return None
        plane = PlaneStore(data_root).plane_for(valid_company_id(company)).ensure()
        with lock_for(_path(plane)):
            rows = _rows(plane)
            rec = next((r for r in rows if r["id"] == tid), None)
            if rec is None or not hmac.compare_digest(rec["hash"], _hash(secret)) or not _active(rec):
                return None
            rec["last_used"] = _now().isoformat(timespec="seconds")
            write_json_atomic(_path(plane), rows)
        return plane, rec
    except (ValueError, LookupError, OSError, PermissionError, RuntimeError):
        return None
