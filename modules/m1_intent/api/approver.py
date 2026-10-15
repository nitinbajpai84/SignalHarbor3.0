"""M1-P09 routes for the named approver, who has no account (M1-26, deck slide 14). A SECURITY PATH.

What the link is: "ap-<session id>-<secret>", made when the organiser sends the draft up. Only its SHA-256 hash is stored
(store/charter.py). It belongs to one session and one draft, expires, can be withdrawn, and is used up by the decision.
How it travels: in the X-Session-Token header only (the header the browser client already sends for a join token, so no new
client code); the page address /approve/<token> carries it to the screen, never to the API, and no API route takes it in a
URL, a query or a body. It is not a participant token: resolve_token() refuses its shape.
What it allows: reading that one draft, and approving or declining it with a comment. The answers hold the charter's own
words and nothing else: no session, company, person or account ids, no other session, no organiser data.
Defences: both routes are `entry` routes in the table (no sign-in needed), so they check everything themselves, in this
order: the failure lock (like sign-in: 5 failures, then a wait), the token's shape, the control index for the company,
that the company still owns the module, and then the hash. Every failure before the hash matches gives the same answer.
"""
import json
import logging

from fastapi import APIRouter, Request

from modules.m1_intent.api import deps
from modules.m1_intent.domain import charter as C
from modules.m1_intent.domain import notes as N
from modules.m1_intent.store.charter import TOKEN, CharterStore
from modules.m1_intent.store.files import StoreError
from modules.m1_intent.store.room import JoinIndex
from sh_platform.auth.sessions import LoginThrottle
from sh_platform.modulegate import may_use_module
from sh_platform.plane import CrossCompanyError, PlaneStore

log = logging.getLogger(__name__)
router = APIRouter()
MODULE = "m1_intent"
BODY_MAX = 16384        # a decision is one word and a comment of a thousand characters
HEADER = "x-session-token"
_INVALID = ("link_invalid", "This link is not working. Please ask for a new one.")
_LOCKED = ("too_many_tries", "Too many tries. Please wait a minute, then open your link again.")
_STATUS = {"link_invalid": 404, "link_gone": 409, "invalid": 422, "comment_needed": 422}
guarded = deps.guarded((C.CharterError, lambda e: deps.plain(_STATUS.get(e.code, 409), e.code, e.message)))


def _throttle(app) -> LoginThrottle:
    """One failure counter per app, keyed by the caller's address. ponytail: behind a proxy every caller shares one
    address; key on the proxy's forwarded address when one is deployed."""
    if getattr(app.state, "approver_throttle", None) is None:
        app.state.approver_throttle = LoginThrottle()
    return app.state.approver_throttle


class _Refuse(Exception):
    def __init__(self, response):
        self.response = response


def _ground(request: Request) -> tuple[CharterStore, str, str, C.CharterSettings]:
    """The store, session id and token of a request that carries a well-formed token for a session whose company still
    owns the module. Every failure counts against the caller and gives one answer."""
    throttle, key = _throttle(request.app), request.client.host if request.client else "unknown"
    if throttle.locked(key):
        raise _Refuse(deps.plain(429, *_LOCKED))

    def refuse(code_msg=_INVALID, status=404):
        throttle.failed(key)
        raise _Refuse(deps.plain(status, *code_msg))

    token = request.headers.get(HEADER, "")
    m = TOKEN.fullmatch(token)
    if not m:
        refuse()
    root = request.app.state.settings.data_root
    try:
        company = JoinIndex(root).company_of(m.group(1))
        if company is None or not may_use_module(request.app.state.entitlements, company, MODULE):
            refuse()
        plane = PlaneStore(root).plane_for(company).ensure()
        settings = C.load_charter_settings(getattr(request.app.state, "m1_contracts_dir", None))
    except (StoreError, LookupError, CrossCompanyError, ValueError, OSError):
        refuse()
    return CharterStore(plane, contracts_dir=getattr(request.app.state, "m1_contracts_dir", None)), m.group(1), token, settings


def _failed_link(request: Request) -> None:
    _throttle(request.app).failed(request.client.host if request.client else "unknown")


def _draft_view(settings: C.CharterSettings, v: dict, extra: dict, spec: N.NoteFields) -> dict:
    """What the approver may see: the draft's own words, the named approver and when the link ends. Nothing else."""
    return {"version": v["version"], "template": v["template"],
            "lists": C.lists([(k["id"], k["heading"]) for k in spec.kinds], [{**p, "id": str(i)} for i, p in enumerate(v["problems"])]),
            "problems": [{"title": p["title"], "kind": p.get("kind", "intent"), "details": p.get("details", []),
                          "priority_label": settings.label(p["priority"]), "so_that": p["so_that"],
                          "note_count": p["note_count"]} for p in v["problems"]],
            "later": [{"title": p["title"]} for p in v["later"]], "footer": v["footer"], **extra}


async def _decision_body(request: Request) -> dict | None:
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        return None
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > BODY_MAX:
        return None
    chunks, size = [], 0
    async for chunk in request.stream():  # counted as it arrives: a missing or false Content-Length does not help
        size += len(chunk)
        if size > BODY_MAX:
            return None
        chunks.append(chunk)
    try:
        body = json.loads(b"".join(chunks))
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


@router.post("/approver/charter")
@guarded
async def read_draft(request: Request):
    try:
        store, session_id, token, settings = await deps.blocking(_ground, request)
    except _Refuse as e:
        return e.response
    try:
        v, extra = await deps.blocking(store.approver_view, session_id, token)
    except C.CharterError:
        _failed_link(request)
        raise
    return _draft_view(settings, v, {"approver_name": extra["approver_name"], "expires_at": extra["expires_at"]},
                       N.load_fields(getattr(request.app.state, "m1_contracts_dir", None)))


@router.post("/approver/decision")
@guarded
async def decide(request: Request):
    try:
        store, session_id, token, settings = await deps.blocking(_ground, request)
    except _Refuse as e:
        return e.response
    body = await _decision_body(request)
    if body is None or set(body) - {"decision", "comment"} or body.get("decision") not in ("approve", "decline"):
        return deps.plain(400, "bad_request", deps.BAD_BODY)
    decision = body["decision"]
    comment = C.clean_comment(body.get("comment"), settings, required=decision == "decline")
    try:
        v = await deps.blocking(store.approver_decide, session_id, token, decision, comment)
    except C.CharterError as e:
        if e.code in ("link_invalid", "link_gone"):
            _failed_link(request)
        raise
    return {"decision": decision, "status": v["status"]}
