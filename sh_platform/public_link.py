"""The full address of a page, for text that leaves the app (an email): the configured base (SH_PUBLIC_BASE_URL) when
set, else this server's own address. The page's Origin is used only when it is exactly one of those two (the organiser's
own page), or, with no configured base, a loopback address when this server is one too (the dev UI's port); any other Origin is ignored. One definition for every module's emails."""
import os
from urllib.parse import urlsplit

from fastapi import Request

_LOOPBACK = {"localhost", "127.0.0.1", "::1"}


def _loopback(url: str) -> bool:
    u = urlsplit(url)  # a bare origin only: no user part, path, query or fragment can ride into an email
    return u.scheme in ("http", "https") and "@" not in u.netloc and not (u.path or u.query or u.fragment) and (u.hostname or "") in _LOOPBACK


def full_url(request: Request, path: str) -> str:
    # without SH_PUBLIC_BASE_URL the base comes from the request's Host header: set it in production
    own = str(request.base_url).rstrip("/")
    base = os.environ.get("SH_PUBLIC_BASE_URL", "").strip().rstrip("/") or own
    origin = (request.headers.get("origin") or "").rstrip("/")
    # dev only (no configured base): the page's own address on this machine (the UI's port) is the one a person can open
    dev = not os.environ.get("SH_PUBLIC_BASE_URL", "").strip() and origin and _loopback(origin) and _loopback(own)
    return f"{origin if origin and (origin in (base, own) or dev) else base}{path}"
