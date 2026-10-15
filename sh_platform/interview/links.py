"""The invite link for one person's interview (LI-INTERVIEW). The pattern is the profile's ask link (sh_platform/profile/asks.py): a token,
only its SHA-256 hash stored, it expires, can be withdrawn, and the secret is shown once. The token names the company (so a guest with no
session can be found) and the row names the one person it answers for; nothing the request says can change either."""
import re
import secrets
from datetime import datetime, timedelta, timezone

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CompanyPlane
from sh_platform.profile import reader
from sh_platform.profile.asks import digest

TOKEN = re.compile(r"iv\.([a-z0-9][a-z0-9-]{0,62})\.([0-9a-f]{32})\.([A-Za-z0-9_-]{43})")
LINK = "/interview/{token}"


def company_of(token: str) -> str | None:
    m = TOKEN.fullmatch(token) if isinstance(token, str) else None
    return m.group(1) if m else None


def _file(plane: CompanyPlane):
    return plane.path("context", "interview", "links.json")


def mint(plane: CompanyPlane, company_id: str, pid: str, now: datetime | None = None) -> str:
    """A new link token for person `pid`. Only the latest link per person is kept; expired ones are dropped."""
    now = now or datetime.now(timezone.utc)
    rid = secrets.token_hex(16)
    token = f"iv.{company_id}.{rid}.{secrets.token_urlsafe(32)}"
    path = _file(plane)
    with lock_for(path):
        rows = [r for r in read_json_strict(path, list) or [] if datetime.fromisoformat(r["expires_at"]) > now and r["person"] != pid]
        rows.append({"id": rid, "person": pid, "hash": digest(token), "at": now.isoformat(), "revoked_at": None,
                     "expires_at": (now + timedelta(hours=reader.contract()["ask"]["link_hours"])).isoformat()})
        write_json_atomic(path, rows)
    return token


def check(plane: CompanyPlane, token: str, now: datetime | None = None) -> str | None:
    """The person a live token answers for, else None (unknown, withdrawn or expired)."""
    now = now or datetime.now(timezone.utc)
    if company_of(token) is None:
        return None
    h = digest(token)
    row = next((r for r in read_json_strict(_file(plane), list) or [] if secrets.compare_digest(r["hash"], h)), None)
    if row is None or row["revoked_at"] or datetime.fromisoformat(row["expires_at"]) <= now:
        return None
    return row["person"]
