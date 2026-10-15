"""The email transport, behind the gateway only (see gateway.send_email for the guards).

When the environment variable SH_SMTP_URL is set (smtp://user:password@host:587, STARTTLS) the message is sent;
otherwise it is written to the plane's outbox/<timestamp>-<id>.eml so a developer can read what would have gone.
The URL is read here and never logged."""
import json
import logging
import os
import smtplib
import ssl
import time
import uuid
from email.message import EmailMessage
from urllib.parse import unquote, urlsplit

from sh_platform.jsonfile import read_json_strict
from sh_platform.plane import CompanyPlane

log = logging.getLogger(__name__)
SMTP_ENV = "SH_SMTP_URL"
OUTBOX_NOTE = "kept in the outbox"


def smtp_configured() -> bool:
    return bool((os.environ.get(SMTP_ENV) or "").strip())


def _domain(address: str) -> str:
    return address.rsplit("@", 1)[-1].strip().lower() if "@" in address else ""


def allowed_domains(plane: CompanyPlane) -> set[str]:
    """`email_domains` from the company's egress policy file; empty means the domains of the company's own accounts."""
    try:
        data = json.loads((plane.area("context") / "egress_policy.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    listed = data.get("email_domains") if isinstance(data, dict) else None
    if isinstance(listed, list) and listed:
        return {d.strip().lower() for d in listed if isinstance(d, str)}
    accounts = read_json_strict(plane.root.parent / "_control" / "accounts.json", list) or []
    return {_domain(a["email"]) for a in accounts if a.get("company_id") == plane.company_id and a.get("email")}


def deliver(plane: CompanyPlane, addresses: list[str], subject: str, body: str) -> str:
    """Send, or keep in the outbox. Returns "sent" or "kept in the outbox"."""
    msg = EmailMessage()
    msg["To"], msg["Subject"] = ", ".join(addresses), subject
    msg.set_content(body)
    url = (os.environ.get(SMTP_ENV) or "").strip()
    if not url:
        out = plane.path("outbox")
        out.mkdir(parents=True, exist_ok=True)
        msg["From"] = "signal-harbor@localhost"
        (out / f"{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}.eml").write_bytes(bytes(msg))
        return OUTBOX_NOTE
    parts = urlsplit(url)
    user = unquote(parts.username or "")
    msg["From"] = user if "@" in user else "signal-harbor@localhost"
    with smtplib.SMTP(parts.hostname, parts.port or 587, timeout=30) as s:
        s.starttls(context=ssl.create_default_context())
        if user:
            s.login(user, unquote(parts.password or ""))
        s.send_message(msg)
    return "sent"
