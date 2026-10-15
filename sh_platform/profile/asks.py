"""Nira asks for what is missing (LI-PROFILE): a short request to the person the people list names as the holder of a missing group.

Nothing is sent. Nira writes the email for the organiser to copy, with a link to upload. The link token follows module 2's owner link
(modules/m2_baseline/domain/requests.py, copied, not imported): "pf-<id>-<secret>", only its SHA-256 hash is stored, it expires, can be
withdrawn, and the secret is shown once. The text holds the group's title only: no figure, no client data.
"""
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CompanyPlane
from sh_platform.profile import reader, store

TOKEN = re.compile(r"pf-([0-9a-f]{32})-([A-Za-z0-9_-]{43})")
LINK = "/company/bring?ask={token}"


def _file(plane: CompanyPlane):
    return plane.path("context", "profile", "asks.json")


def digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _v(item: dict, key: str):
    c = item.get(key)
    return c.get("value") if isinstance(c, dict) else None


def holder(doc: dict, g: dict) -> dict | None:
    """The person whose role or team matches the group's holder words; else the organiser; else nobody is named yet."""
    people = list(doc["people"].values())
    words = [w for w in g["holder"]]
    for p in people:
        keys = " ".join(w for w, f in (("sponsor", "is_sponsor"), ("head of data", "is_head_of_data"), ("organiser", "is_organiser")) if _v(p, f) is True)
        have = reader._norm(f"{_v(p, 'role') or ''} {_v(p, 'team') or ''} {keys}")
        if any(re.search(rf"\b{re.escape(w)}\b", have) for w in words):
            return _card(p)
    org = next((p for p in people if _v(p, "is_organiser") is True), None)
    return _card(org) if org else None


def _card(p: dict) -> dict:
    return {"name": _v(p, "name"), "role": _v(p, "role"), "email": _v(p, "email")}


def email_text(person: str | None, organiser: str, title: str, link: str | None = None) -> dict:
    who = (person or "there").strip()
    return {"subject": f"One thing for Signal Harbor: {title.lower()}",
            "body": (f"Hello {who},\n\n{organiser} asked me to ask you for one thing so we can start: {title.lower()}. "
                     f"Any form is fine (Excel, CSV, PDF, Word or an email export). If you do not have it, tell us and we will ask one short question instead.\n\n"
                     f"Upload it here: {link or '{link}'}\n\n"
                     "Your file stays on your company's machine; our agents see only masked passages, column names and counts. "
                     "No data is sent with this message.\n\nThank you,\nNira")}


def missing(plane: CompanyPlane, organiser: str = "your organiser") -> list[dict]:
    """One ask per missing required group, with who holds it and the text to copy (the link is minted by `mint`)."""
    doc, out = store.load(plane), []
    for g in reader.groups():
        state = ((doc["inputs"].get(f"g{g['id']}") or {}).get("state") or {}).get("value") or "missing"
        if state == "missing" and g["required"]:
            h = holder(doc, g)
            out.append({"group": g["id"], "title": g["title"], "holder": h, "email": email_text(h and h["name"], organiser, g["title"])})
    return out


def mint(plane: CompanyPlane, gid: int, now: datetime | None = None, person: str = "") -> str:
    """A new link token for group `gid` and the person asked; its hash is kept, the token is returned once. Only the latest ask per group
    and person is kept (an older one stops working), and expired ones are dropped, so the file cannot grow without end."""
    reader.group(gid)
    now = now or datetime.now(timezone.utc)
    rid = secrets.token_hex(16)
    token = f"pf-{rid}-{secrets.token_urlsafe(32)}"
    path = _file(plane)
    with lock_for(path):
        rows = [r for r in read_json_strict(path, list) or []
                if datetime.fromisoformat(r["expires_at"]) > now and (r["group"], r.get("person", "")) != (gid, person)]
        rows.append({"id": rid, "group": gid, "person": person, "hash": digest(token), "at": now.isoformat(), "revoked_at": None,
                     "expires_at": (now + timedelta(hours=reader.contract()["ask"]["link_hours"])).isoformat()})
        write_json_atomic(path, rows)
    return token


def check(plane: CompanyPlane, token: str, now: datetime | None = None) -> int | None:
    """The group a live token is for, else None (unknown, withdrawn or expired)."""
    now = now or datetime.now(timezone.utc)
    if not isinstance(token, str) or not TOKEN.fullmatch(token):
        return None
    h = digest(token)
    row = next((r for r in read_json_strict(_file(plane), list) or [] if secrets.compare_digest(r["hash"], h)), None)
    if row is None or row["revoked_at"] or datetime.fromisoformat(row["expires_at"]) <= now:
        return None
    return row["group"]


def with_link(text: dict, token: str) -> dict:
    link = LINK.format(token=token)
    return {**text, "body": text["body"].replace("{link}", link), "link": link}
