"""Harbor 3.0 public API for Consume (plan: docs/v3/PROGRAM-GAPS.md W6; examples: docs/v3/API.md).

A read-only REST door for a client's own tools, under /api/public/v1, opened by an API key an office admin makes on the Build page:
- a key belongs to one company and is `shpub.<company>.<key_id>.<secret>`; only the sha256 of the secret is kept, and the key is shown once;
- scopes are figures, ask, signals, documents; a key may also carry entity ids, and a family-member key must (it sees only its own share);
- every call is checked first (key, scope, rate limit) and then logged (key id, route, time, status) in the company's plane;
- a key only ever opens its own company's plane, because the company is read out of the key and the plane is the only place it looks;
- a webhook per key hears "signal fired", delivered through the egress gateway (host on the webhook list, names tokenised) and signed with HMAC.
Entity rule: an item that carries entity ids is shown only when one of them is in the key's list; an item that carries none is withheld from a key that has a list.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import secrets
import threading
import time
from collections import deque
from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import PlaneStore, valid_company_id

log = logging.getLogger(__name__)
SCOPES = ("figures", "ask", "signals", "documents")
KINDS = ("company", "family")
DEFAULT_RATE, MAX_RATE = 60, 600  # calls a minute
MAX_KEYS = 25
PREFIX = "shpub"
WINDOW = 60.0
_HITS: dict[tuple, deque] = {}
_HITS_LOCK = threading.Lock()


class KeyError_(ValueError):
    """Safe to show."""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def _dir(plane):
    d = plane.path("v3", "api")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _keys_path(plane):
    return _dir(plane) / "keys.json"


def _calls_path(plane):
    return _dir(plane) / "calls.jsonl"


def _rows(plane) -> list[dict]:
    try:
        return read_json_strict(_keys_path(plane), list) or []
    except (OSError, ValueError):
        return []


def public(r: dict) -> dict:
    wh = r.get("webhook")
    return {"id": r["id"], "label": r["label"], "kind": r["kind"], "member": r.get("member"), "scopes": r["scopes"], "entity_ids": r["entity_ids"],
            "rate_per_min": r["rate_per_min"], "created": r["created"], "created_by": r.get("created_by"), "revoked": r["revoked"],
            "webhook": {"url": wh["url"]} if wh else None}


# ---- keys --------------------------------------------------------------------------------------------------------------------------------

def issue(plane, by: str, label, scopes, entity_ids=None, kind: str = "company", member=None, rate_per_min=DEFAULT_RATE) -> dict:
    """The public record plus `key` (the only time the key is visible)."""
    label = " ".join(str(label or "").split())[:60]
    if not label:
        raise KeyError_("Give the key a name, such as the tool it is for.")
    if not isinstance(scopes, (list, tuple)) or not scopes or not all(isinstance(s, str) for s in scopes) or set(scopes) - set(SCOPES):
        raise KeyError_("Scopes are figures, ask, signals and documents.")
    if kind not in KINDS:
        raise KeyError_("A key is for the company or for a family member.")
    ids = entity_ids if entity_ids is not None else []
    if not isinstance(ids, (list, tuple)) or not all(isinstance(e, str) and re.fullmatch(r"[\w .:-]{1,80}", e) for e in ids):
        raise KeyError_("Entity ids are a list of entity codes.")
    ids = sorted(set(ids))
    if kind == "family":
        member = " ".join(str(member or "").split())[:80]
        if not ids and member:
            ids = family_entities(plane, member)  # the signed family_access_<member>_<entity> rules, when the office has them
        if not ids:
            raise KeyError_("A family-member key needs the entities that member may see.")
        if "ask" in scopes:
            raise KeyError_("A family-member key cannot ask: an answer is worked out over the whole office.")
    elif ids and "ask" in scopes:
        raise KeyError_("A key limited to some entities cannot ask: an answer is worked out over the whole office.")
    if not isinstance(rate_per_min, int) or isinstance(rate_per_min, bool) or not 1 <= rate_per_min <= MAX_RATE:
        raise KeyError_(f"A key may make 1 to {MAX_RATE} calls a minute.")
    kid, secret = secrets.token_hex(6), secrets.token_urlsafe(32)
    rec = {"id": kid, "label": label, "kind": kind, "member": member if kind == "family" else None, "scopes": sorted(set(scopes)), "entity_ids": ids,
           "rate_per_min": rate_per_min, "hash": _hash(secret), "created": now(), "created_by": by, "revoked": False, "webhook": None}
    with lock_for(_keys_path(plane)):
        rows = _rows(plane)
        if sum(1 for r in rows if not r["revoked"]) >= MAX_KEYS:
            raise KeyError_("Revoke a key you no longer use first.")
        write_json_atomic(_keys_path(plane), rows + [rec])
    return {**public(rec), "key": f"{PREFIX}.{plane.company_id}.{kid}.{secret}"}


def listing(plane) -> list[dict]:
    return [public(r) for r in _rows(plane)]


def revoke(plane, key_id: str) -> bool:
    with lock_for(_keys_path(plane)):
        rows = _rows(plane)
        hit = [r for r in rows if r["id"] == key_id and not r["revoked"]]
        for r in hit:
            r["revoked"], r["webhook"] = True, None
        if hit:
            write_json_atomic(_keys_path(plane), rows)
    return bool(hit)


def family_entities(plane, member: str) -> list[str]:
    """Entity codes a family member may see at full or summary, from the signed (approved) family_access_<member>_<entity> rules. [] when there are none."""
    slug = re.sub(r"[^a-z0-9]+", "_", member.lower()).strip("_")
    try:
        from sh_platform.v1 import wh
        with wh.connect(plane, read_only=True) as con:
            rows = con.execute(
                "select e.entity_code, p.level from legal_entities as e join (select r.rule_code, json_extract_string(v.parameters, '$.level') as level "
                "from business_rules as r join rule_versions as v on v.business_rule_id = r.id where starts_with(r.rule_code, 'family_access_') "
                "and v.approval_status = 'approved' qualify row_number() over (partition by r.rule_code order by v.version_number desc) = 1) as p "
                "on p.rule_code = 'family_access_' || ? || '_' || trim(regexp_replace(lower(e.entity_code), '[^a-z0-9]+', '_', 'g'), '_')", [slug]).fetchall()
    except Exception:  # noqa: BLE001 - no warehouse or no rules yet: the admin lists the entities by hand
        log.info("family access rules could not be read", exc_info=True)
        return []
    return sorted({str(c) for c, level in rows if level in ("full", "summary")})


def verify(data_root, text: str):
    """(plane, rec, ok): the key's plane and record when the key id exists there (ok is False for a wrong secret or a revoked key), else (None, None, False).
    Only the company named in the key is opened, and only to look the key id up."""
    try:
        prefix, company, kid, secret = str(text or "").split(".", 3)
        if prefix != PREFIX or len(text) > 200:
            return None, None, False
        plane = PlaneStore(data_root).plane_for(valid_company_id(company)).ensure()
        rec = next((r for r in _rows(plane) if r["id"] == kid), None)
        if rec is None:
            return None, None, False
        return plane, rec, hmac.compare_digest(rec["hash"], _hash(secret)) and not rec["revoked"]
    except (ValueError, LookupError, OSError, PermissionError, RuntimeError):
        return None, None, False


# ---- rate limit and the call log ---------------------------------------------------------------------------------------------------------

def allow(plane, rec: dict, at: float | None = None) -> bool:
    """A sliding minute per key. ponytail: in memory, per process; a shared store if the API runs on several processes."""
    at = time.monotonic() if at is None else at
    with _HITS_LOCK:
        q = _HITS.setdefault((str(plane.path("v3")), rec["id"]), deque())
        while q and at - q[0] >= WINDOW:
            q.popleft()
        if len(q) >= rec["rate_per_min"]:
            return False
        q.append(at)
        return True


def log_call(plane, key_id: str, route: str, status: int) -> None:
    line = json.dumps({"key": key_id, "route": route, "at": now(), "status": status})
    with lock_for(_calls_path(plane)):
        with open(_calls_path(plane), "a", encoding="utf-8") as f:
            f.write(line + "\n")


def calls(plane, key_id: str | None = None, limit: int = 50) -> list[dict]:
    try:
        lines = _calls_path(plane).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = [r for r in (json.loads(x) for x in lines if x.strip()) if not key_id or r["key"] == key_id]
    return list(reversed(out[-limit:]))


class Ctx:
    def __init__(self, plane, rec):
        self.plane, self.rec, self.status = plane, rec, 200

    def sees(self, entities) -> bool:
        ids = self.rec["entity_ids"]
        if not ids:
            return True
        return bool(set(ids) & {str(e) for e in (entities or [])})


def gate(scope: str | None):
    """A FastAPI dependency for one public route: checks the key, its scope and its rate, and logs the call with the status it ended with.
    Failures are 401 (no or wrong or revoked key), 403 (scope), 429 (rate). A key that does not exist in the company it names is not logged anywhere."""
    def dep(request: Request):
        auth = request.headers.get("authorization", "")
        bearer = auth[7:].strip() if auth[:7].lower() == "bearer " else ""
        plane, rec, ok = verify(request.app.state.settings.data_root, bearer)
        route = f"{request.method} {request.scope['route'].path_format}"

        def refuse(status, message, headers=None):
            if rec is not None:
                log_call(plane, rec["id"], route, status)
            raise HTTPException(status, {"error": {401: "unauthorized", 403: "scope_not_granted", 429: "rate_limited"}[status], "message": message}, headers=headers)
        if not ok:
            refuse(401, "The API key is missing, wrong or revoked.", {"WWW-Authenticate": 'Bearer realm="signal-harbor"'})
        if scope and scope not in rec["scopes"]:
            refuse(403, f"This key does not have the {scope} scope.")
        if not allow(plane, rec):
            refuse(429, f"This key may make {rec['rate_per_min']} calls a minute. Try again shortly.", {"Retry-After": "60"})
        ctx = Ctx(plane, rec)
        try:
            yield ctx
        except HTTPException as e:
            ctx.status = e.status_code
            raise
        except RequestValidationError:
            ctx.status = 422
            raise
        except Exception:
            ctx.status = 500
            raise
        finally:
            log_call(plane, rec["id"], route, ctx.status)
    return dep


# ---- what the routes return --------------------------------------------------------------------------------------------------------------

def _entities(item: dict):
    return item.get("entity_ids") or ([item["entity_id"]] if item.get("entity_id") else [])


def figure_row(ctx: Ctx, rec: dict) -> dict | None:
    if not ctx.sees(_entities(rec)):
        return None
    from sh_platform.v1 import v3_figstore as FS
    r = FS.row(rec)
    return {"id": r["id"], "name": r["name"], "definition": rec.get("definition") or "", "grain": rec.get("grain") or [], "version": r["current_v"],
            "status": r["status"], "last_run_at": r["last_run_at"], "held": bool(r["hold"])}


def figures(ctx: Ctx) -> list[dict]:
    from sh_platform.v1 import v3_figstore as FS
    return [x for rec in FS.every(ctx.plane) if (x := figure_row(ctx, rec))]


def figure(ctx: Ctx, figure_id: str) -> dict:
    from sh_platform.v1 import v3_figstore as FS
    rec = FS.read(ctx.plane, figure_id)
    head = figure_row(ctx, rec) if rec else None
    if head is None:
        raise HTTPException(404, {"error": "not_found", "message": "No such figure."})
    ver = FS.version(rec) or {}
    receipts = {"built_from": ver.get("built_from"), "reads": ver.get("reads") or [], "sql_hash": ver.get("sql_hash"), "tie_out": ver.get("tie_out"),
                "assumptions": ver.get("assumptions") or [], "runs": ver.get("runs") or [], "approved_at": ver.get("approved_at"),
                "versions": [{"v": v["v"], "status": v["status"]} for v in rec["versions"]]}
    return {**head, "receipts": receipts, "lineage": FS.lineage(ctx.plane, rec)}


SIGNAL_KEYS = ("id", "signal", "title", "subject", "severity", "route_to", "status", "at", "message", "evidence")


def signal_row(r: dict) -> dict:
    return {k: r.get(k) for k in SIGNAL_KEYS}  # no person, no event body, no values


def signals(ctx: Ctx, status: str | None = None) -> list[dict]:
    from sh_platform.v1 import v3_signals as SG
    rows = [signal_row(r) for r in SG.fired(ctx.plane) if ctx.sees(_entities(r)) and (not status or r["status"] == status)]
    return list(reversed(rows))


DOC_KEYS = ("id", "title", "document_type", "original_filename", "instrument_name", "valuation_date", "received_at", "document_status", "label")


def documents(ctx: Ctx) -> list[dict]:
    """Metadata only: no file bytes and no storage path."""
    from sh_platform.v1 import e2_screen as S
    viewer = viewer_of_key(ctx.rec)
    return [{k: d.get(k) for k in DOC_KEYS} for d in S.rows(ctx.plane, viewer) if ctx.sees(_entities(d))]


def viewer_of_key(rec: dict):
    """A key reads as a consumer of the office with no named seat: the least a person can be (participant)."""
    from sh_platform.profile.view import Viewer
    return Viewer(f"API key {rec['label']}", frozenset({"participant"}), False, f"apikey-{rec['id']}")


def ask(ctx: Ctx, text: str) -> dict:
    """The same answer path as the Consume page (v3_board_routes: kept per question and data version, figures first, then Lumen)."""
    from sh_platform.v1 import v3_board_routes as B, v3_consume as C
    viewer = viewer_of_key(ctx.rec)
    th = B._live(ctx.plane, text)
    pid = th["pid"] if th else None
    got = C.answer(ctx.plane, viewer, text, lambda: B._ask(ctx.plane, viewer, text, pid))
    return {k: got.get(k) for k in ("answer", "figure", "trace", "used", "cached", "ms", "as_of")}


# ---- webhooks ----------------------------------------------------------------------------------------------------------------------------

def set_webhook(plane, key_id: str, url: str) -> dict:
    """Register the one URL that hears "signal fired" for this key. Returns {url, secret, allowed}: the secret is shown once, and `allowed` says
    whether the URL's host is already on the company's webhook list (nothing is sent to a host that is not)."""
    p = urlsplit(str(url or "").strip())
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.fragment or len(url) > 500:
        raise KeyError_("A webhook is an https address, such as https://example.com/hooks/harbor.")
    secret = secrets.token_urlsafe(32)
    with lock_for(_keys_path(plane)):
        rows = _rows(plane)
        rec = next((r for r in rows if r["id"] == key_id and not r["revoked"]), None)
        if rec is None or "signals" not in rec["scopes"]:
            raise KeyError_("The key needs the signals scope to have a webhook.")
        rec["webhook"] = {"url": url.strip(), "secret": secret}
        write_json_atomic(_keys_path(plane), rows)
    from sh_platform.egress.policy import EgressPolicy
    return {"url": url.strip(), "secret": secret, "allowed": p.hostname.lower() in EgressPolicy(plane).webhook_hosts()}


def clear_webhook(plane, key_id: str) -> bool:
    with lock_for(_keys_path(plane)):
        rows = _rows(plane)
        hit = [r for r in rows if r["id"] == key_id and r.get("webhook")]
        for r in hit:
            r["webhook"] = None
        if hit:
            write_json_atomic(_keys_path(plane), rows)
    return bool(hit)


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _post(url: str, body: bytes, headers: dict) -> str:
    import httpx
    with httpx.Client(timeout=10.0, follow_redirects=False) as c:
        r = c.post(url, content=body, headers=headers)
        r.raise_for_status()
        return "ok"


def notify_signal(plane, card: dict, post=None) -> list[dict]:
    """Tell every key's webhook that a signal fired. Goes out through the egress gateway (send_webhook: https, host on the webhook list, names tokenised,
    logged) and carries X-Harbor-Signature: sha256=HMAC(secret, exact body sent). `post(url, body, headers)` replaces the real HTTP call (tests).
    Returns one {key, ok, why?} per webhook; never raises."""
    from sh_platform.egress import gateway as G
    from sh_platform.egress.errors import EgressBlocked
    out = []
    for rec in _rows(plane):
        wh = rec.get("webhook")
        if rec["revoked"] or not wh or "signals" not in rec["scopes"] or not Ctx(plane, rec).sees(_entities(card)):
            continue

        def transport(url, body, secret=wh["secret"]):
            return (post or _post)(url, body, {"content-type": "application/json", "x-harbor-event": "signal.fired", "x-harbor-signature": sign(secret, body)})
        try:
            G.send_webhook(plane, wh["url"], {"event": "signal.fired", "signal": {k: card.get(k) for k in ("id", "signal", "title", "subject", "severity", "route_to", "at", "message")}},
                           transport=transport, module_id="public_api")
            out.append({"key": rec["id"], "ok": True})
        except EgressBlocked as e:
            out.append({"key": rec["id"], "ok": False, "why": getattr(e, "reason_code", "blocked")})
        except Exception:  # noqa: BLE001 - a webhook never stops a signal
            log.warning("webhook failed", exc_info=True)
            out.append({"key": rec["id"], "ok": False, "why": "error"})
    return out


def announce(plane, card: dict) -> None:
    """Called when a signal fires (v3_signals.evaluate): delivery runs on its own thread so the evaluation never waits on a customer's server."""
    if any(r.get("webhook") and not r["revoked"] for r in _rows(plane)):
        threading.Thread(target=notify_signal, args=(plane, card), daemon=True).start()
