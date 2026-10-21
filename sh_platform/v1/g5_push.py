"""G5 Web Push: the subscription store, a minimal VAPID sender and the pass that tells people about new Action cards and approvals.

pywebpush is not in the venv, so this is a minimal VAPID sender (RFC 8292, ES256 token signed with `cryptography`) that sends a push with NO body.
The browser wakes the service worker (ui/public/sw.js), which asks `GET /api/v3/push/inbox` for the words, so nothing readable ever crosses the
push service. Keys come from the environment by name: SH_VAPID_PUBLIC_KEY, SH_VAPID_PRIVATE_KEY (base64url) and SH_VAPID_SUBJECT (mailto: or https:).
Without them, simple mode makes a dev pair once in <data root>/_control/vapid_dev.json (outside the repo); production mode makes none and push stays off.
The endpoint a browser hands us is only called when its host is a known push service (SH_PUSH_HOSTS adds more, comma separated).

Files, per company, under portal/: push_subscriptions.json {account_id: [{endpoint, at}]}, push_inbox.json {account_id: [{title, body, url, at}]},
push_seen.json [ids already announced]. The first pass only records what is already there (no blast on switch-on).
ponytail: one pass reads whole small files; a database table when a company has thousands of subscribers.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from urllib.parse import urlsplit

from sh_platform import mode as _mode
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
ENV_PUB, ENV_PRIV, ENV_SUB, ENV_HOSTS = "SH_VAPID_PUBLIC_KEY", "SH_VAPID_PRIVATE_KEY", "SH_VAPID_SUBJECT", "SH_PUSH_HOSTS"
PUSH_HOSTS = ("fcm.googleapis.com", "updates.push.services.mozilla.com", "push.apple.com", "notify.windows.com", "push.services.mozilla.com")
MAX_SUBS, MAX_INBOX, TTL = 5, 20, 3600


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# ---- keys -------------------------------------------------------------------------------------------------------------------------------

def _make_pair() -> dict:
    from cryptography.hazmat.primitives import serialization as S
    from cryptography.hazmat.primitives.asymmetric import ec
    k = ec.generate_private_key(ec.SECP256R1())
    pub = k.public_key().public_bytes(S.Encoding.X962, S.PublicFormat.UncompressedPoint)
    return {"public": _b64(pub), "private": _b64(k.private_numbers().private_value.to_bytes(32, "big"))}


def vapid(plane) -> dict | None:
    """{public, private, subject} from the environment, else the dev pair (simple mode only), else None (push is off)."""
    pub, priv = (os.environ.get(ENV_PUB) or "").strip(), (os.environ.get(ENV_PRIV) or "").strip()
    subject = (os.environ.get(ENV_SUB) or "").strip() or "mailto:signal-harbor@localhost"
    if pub and priv:
        return {"public": pub, "private": priv, "subject": subject}
    if _mode.production():
        return None
    f = plane.root.parent / "_control" / "vapid_dev.json"
    with lock_for(f):
        pair = read_json_strict(f, dict)
        if not pair:
            f.parent.mkdir(parents=True, exist_ok=True)
            pair = _make_pair()
            write_json_atomic(f, pair)
    return {**pair, "subject": subject}


def _token(keys: dict, endpoint: str) -> str:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    u = urlsplit(endpoint)
    head = _b64(json.dumps({"typ": "JWT", "alg": "ES256"}).encode())
    body = _b64(json.dumps({"aud": f"{u.scheme}://{u.netloc}", "exp": int(time.time()) + 12 * 3600, "sub": keys["subject"]}).encode())
    key = ec.derive_private_key(int.from_bytes(_unb64(keys["private"]), "big"), ec.SECP256R1())
    r, s = decode_dss_signature(key.sign(f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256())))
    return f"{head}.{body}.{_b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


# ---- the store --------------------------------------------------------------------------------------------------------------------------

def _f(plane, name: str):
    d = plane.path("portal")
    d.mkdir(parents=True, exist_ok=True)
    return d / name


def _read(plane, name: str, kind: type):
    try:
        return read_json_strict(_f(plane, name), kind) or kind()
    except (OSError, ValueError):
        return kind()


def host_ok(endpoint: str) -> bool:
    u = urlsplit(str(endpoint))
    extra = tuple(h.strip().lower() for h in (os.environ.get(ENV_HOSTS) or "").split(",") if h.strip())
    h = (u.hostname or "").lower()
    return u.scheme == "https" and any(h == k or h.endswith("." + k) for k in PUSH_HOSTS + extra) and len(str(endpoint)) < 1000


def subscribe(plane, account_id: str, sub: dict) -> bool:
    """False when the endpoint is not a push service we will call."""
    ep = str((sub or {}).get("endpoint") or "")
    if not host_ok(ep):
        return False
    f = _f(plane, "push_subscriptions.json")
    with lock_for(f):
        d = _read(plane, "push_subscriptions.json", dict)
        mine = [s for s in d.get(account_id, []) if s["endpoint"] != ep]
        d[account_id] = ([{"endpoint": ep, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}] + mine)[:MAX_SUBS]
        write_json_atomic(f, d)
    return True


def unsubscribe(plane, account_id: str, endpoint: str | None = None) -> None:
    f = _f(plane, "push_subscriptions.json")
    with lock_for(f):
        d = _read(plane, "push_subscriptions.json", dict)
        d[account_id] = [s for s in d.get(account_id, []) if endpoint and s["endpoint"] != endpoint]
        write_json_atomic(f, {k: v for k, v in d.items() if v})


def subscriptions(plane) -> dict:
    return _read(plane, "push_subscriptions.json", dict)


def is_on(plane, account_id: str) -> bool:
    return bool(subscriptions(plane).get(account_id))


def inbox_take(plane, account_id: str) -> list[dict]:
    """The words behind a wake-up: what the person has not yet been shown. Emptied by the read."""
    f = _f(plane, "push_inbox.json")
    with lock_for(f):
        d = _read(plane, "push_inbox.json", dict)
        got = d.pop(account_id, [])
        write_json_atomic(f, d)
    return got


def _leave(plane, account_id: str, title: str, body: str, url: str) -> None:
    f = _f(plane, "push_inbox.json")
    with lock_for(f):
        d = _read(plane, "push_inbox.json", dict)
        d[account_id] = ([{"title": title, "body": body, "url": url, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}] + d.get(account_id, []))[:MAX_INBOX]
        write_json_atomic(f, d)


# ---- sending ----------------------------------------------------------------------------------------------------------------------------

def send_one(plane, endpoint: str) -> int:
    """POST the empty push. Returns the HTTP status (0 when it could not be reached). Tests replace this with a fake."""
    keys = vapid(plane)
    if keys is None or not host_ok(endpoint):
        return 0
    import httpx
    try:
        r = httpx.post(endpoint, headers={"Authorization": f"vapid t={_token(keys, endpoint)}, k={keys['public']}", "TTL": str(TTL), "Content-Length": "0"},
                       timeout=10, follow_redirects=False)
        return r.status_code
    except httpx.HTTPError:
        log.info("push to %s did not reach", urlsplit(endpoint).hostname)
        return 0


def notify(plane, account_id: str, title: str, body: str, url: str) -> int:
    """Leave the words in the inbox and wake every device of the account. Returns how many devices the push service took. Gone devices (404/410) are dropped."""
    subs = subscriptions(plane).get(account_id) or []
    if not subs:
        return 0
    _leave(plane, account_id, title, body, url)
    sent = 0
    for s in subs:
        code = send_one(plane, s["endpoint"])
        if code in (404, 410):
            unsubscribe(plane, account_id, s["endpoint"])
        elif 200 <= code < 300:
            sent += 1
    return sent


# ---- the pass: new Action cards and approvals -------------------------------------------------------------------------------------------

def _items(plane, accounts: list[dict]) -> list[dict]:
    """[{id, title, body, url, to: [account_id]}]: open signal cards for the admins and the routed role, pending approvals for the member."""
    from sh_platform.v1 import g5_portal as G, v3_roles as R, v3_signals as SG
    jobs = R._jobs(plane)
    out = []
    for c in SG.fired(plane):
        if c.get("status") != "open":
            continue
        to = [a["account_id"] for a in accounts if "company_admin" in a["roles"] or jobs.get(str(a.get("email") or "").casefold()) == c.get("route_to")]
        out.append({"id": "card:" + c["id"], "title": "Needs you", "body": str(c.get("title") or "A new card is waiting"), "url": "/v3/action", "to": to})
    for ap in G.approvals_all(plane):
        if ap["status"] == "pending":
            to = [a["account_id"] for a in accounts if G.member_of(plane, a) == ap["member"]]
            out.append({"id": "approval:" + ap["id"], "title": "Approval for you", "body": ap["title"], "url": "/v3/portal#approvals", "to": to})
    return out


def tick(plane, accounts: list[dict]) -> int:
    """Announce what is new since the last pass. Returns the number of devices told. The first pass only records what is there."""
    items, f = _items(plane, accounts), _f(plane, "push_seen.json")
    with lock_for(f):
        first = not f.is_file()
        seen = set(_read(plane, "push_seen.json", list))
        new = [i for i in items if i["id"] not in seen]
        write_json_atomic(f, sorted(seen | {i["id"] for i in items}))
    return 0 if first else sum(notify(plane, a, i["title"], i["body"], i["url"]) for i in new for a in i["to"])
