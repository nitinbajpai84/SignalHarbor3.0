"""Layer 2 of spec 14: is this person in this intent, and in what role. Runs after the module gate and the role guard.

How to use it in your card's router (copy this):

    from fastapi import APIRouter, Depends
    from sh_platform.intents.access import IntentAccess, IntentRoute, intent_roles, CONTENT, CLOSER

    router = APIRouter(route_class=IntentRoute)   # refusals come back as {"error", "message"}, like the guard's 403

    @router.get("/api/intents/{intent_id}/cards")
    def cards(a: IntentAccess = Depends(intent_roles(CONTENT))):
        a.intent, a.roles, a.plane   # the record, the viewer's role set, the company plane

    @router.post("/api/intents/{intent_id}/closure/confirm")
    def confirm(a: IntentAccess = Depends(intent_roles(CLOSER, code="intent_not_your_close"))): ...

Inside a handler that already holds the record: `roles = require_intent_role(request, intent, CONTENT)`.
Without raising (lists, Pulse lines): `roles_of(intent, me)` where `me = Me.of(request, plane)`; empty means "may not know it exists".

Role names: creator (of a draft), organiser, closer, participant, affected, observer, area_member, company_admin, share_visitor, plus
the derived `content` (may open the content). A write (any method but GET/HEAD) on a closed or cancelled intent is refused with
`intent_closed` once the role passes. Refusal codes and words are file 14's "Error copy"; none is `forbidden`.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from sh_platform.intents import _plane, _viewer
from sh_platform.jsonfile import read_json_strict
from sh_platform.plane import CompanyPlane, CrossCompanyError
from sh_platform.profile import links, store
from sh_platform.profile.view import norm

log = logging.getLogger(__name__)
router = APIRouter()  # no routes of its own; kept so app.py's include stays valid

# ---- role sets per action (file 14, "Per-intent role against action")
ORGANISER = frozenset({"organiser"})
CLOSER = frozenset({"closer"})
PARTICIPANT = frozenset({"participant"})
EXISTENCE = frozenset({"organiser", "closer", "participant", "affected", "observer", "area_member", "company_admin", "share_visitor"})
CLOCK_AND_PEOPLE = frozenset({"organiser", "closer", "participant", "affected", "observer"})
OUTCOME = EXISTENCE  # once closed; the handler checks the state
CONTENT = frozenset({"content"})
CONTRIBUTE = frozenset({"organiser", "participant"})
FEEL = frozenset({"participant", "affected"})
NOTE = frozenset({"affected"})
JOIN_REQUEST = frozenset({"affected", "area_member"})
FOLLOW = frozenset({"affected", "observer"})
EDIT = ORGANISER
STAGE = ORGANISER
STAGE_BUILD_READY = frozenset({"organiser", "closer"})
EXTEND = ORGANISER
EXTEND_DECIDE = CLOSER
CONFIRM_CLOSURE = CLOSER  # with code="intent_not_your_close"
RATE = PARTICIPANT
SHARE = ORGANISER
LINK = frozenset({"organiser", "closer"})
HANDOFF = frozenset({"closer", "company_admin"})  # the company admin acts for the sponsor (rule 6)


def cancel_roles(intent: dict) -> frozenset[str]:
    """Initiative: the sponsor (closer) cancels; every other type: the organiser."""
    return CLOSER if intent.get("type") == "initiative" else ORGANISER


_CONTENT_ROLES = {"creator", "organiser", "closer", "participant", "observer", "share_visitor"}
_WRITERS = {"creator", "organiser", "closer", "participant"}
_CLOSER_SLOT = {"initiative": ("sponsor",), "decision": ("decider",), "problem": ("owner", "reporter"),
                "brainstorm": ("organiser",), "pulse": ("organiser",)}
FROZEN = ("closed", "cancelled")

# ---- error copy (file 14)
NOT_FOUND = "We could not find that."
READ_ONLY = "You can read this intent but not change it."
CLOSED = "This intent is closed. It is kept as it was and cannot be changed."
UNREADABLE = "This intent could not be read. Please tell your administrator."  # file 01


class IntentRefused(HTTPException):
    """A layer-2 or layer-3 refusal. `detail` is the flat body {"error", "message", ...}."""

    def __init__(self, status: int, code: str, message: str, **extra):
        super().__init__(status, detail={"error": code, "message": message, **extra})


def refused_response(exc: IntentRefused) -> JSONResponse:
    return JSONResponse(exc.detail, status_code=exc.status_code)


class IntentRoute(APIRoute):
    """Route class that turns IntentRefused (also raised from a dependency) into the flat body."""

    def get_route_handler(self):
        inner = super().get_route_handler()

        async def handler(request: Request):
            try:
                return await inner(request)
            except IntentRefused as exc:
                return refused_response(exc)
        return handler


def install(app: FastAPI) -> None:
    """Optional, app-wide: the same flat body for routers that do not use IntentRoute."""
    app.add_exception_handler(IntentRefused, lambda _r, exc: refused_response(exc))


@dataclass(frozen=True)
class Me:
    """The viewer as layer 2 needs them: account, linked profile person, that person's areas, company roles."""
    account_id: str | None
    name: str
    roles: frozenset[str]
    shared_name: bool = False
    person_id: str | None = None
    areas: frozenset[str] = frozenset()

    @classmethod
    def of(cls, request: Request, plane: CompanyPlane) -> "Me":
        return cls.for_viewer(plane, _viewer(request))

    @classmethod
    def for_viewer(cls, plane: CompanyPlane, v) -> "Me":
        """The same, from a Viewer already in hand (modules that work below the request, such as North)."""
        pid, areas = person_of(plane, v.account_id)
        return cls(v.account_id, v.name, v.roles, v.shared_name or name_twin(plane, v.name, pid), pid, areas)


def name_twin(plane: CompanyPlane, name: str, mine: str | None) -> bool:
    """Another profile person carries this name (accounts alone miss people with no account). With no linked person of my
    own, an unlinked person of my name may be me, so only a person linked to another account counts."""
    for pid, p in store.raw(plane)["people"].items():
        cell = p.get("name")
        same = isinstance(cell, dict) and bool(name) and norm(cell.get("value") or "") == norm(name)
        if same and pid != mine and (mine or links._account_of(p)):
            return True
    return False


def person_of(plane: CompanyPlane, account_id: str | None) -> tuple[str | None, frozenset[str]]:
    """The profile person linked to this account (LI-LINK) and their areas (`people.<pid>.areas`, admin-stated only)."""
    if not account_id:
        return None, frozenset()
    for pid, p in store.raw(plane)["people"].items():
        if links._account_of(p) == account_id:
            cell = p.get("areas")
            stated = isinstance(cell, dict) and cell.get("mark") == "stated" and isinstance(cell.get("value"), list)
            return pid, frozenset(norm(a) for a in cell["value"]) if stated else frozenset()
    return None, frozenset()


def _entries(slot) -> list:
    return [e for e in (slot if isinstance(slot, list) else [slot]) if e]


def _is_me(entry, me: Me) -> bool:
    """A person entry is a person id or account id string, or {account_id, person_id, name}. The account wins; a name alone
    matches only when nobody else in the company carries it (as profile/view.py)."""
    if isinstance(entry, str):
        return entry in {me.account_id, me.person_id} - {None}
    if not isinstance(entry, dict):
        return False
    if entry.get("account_id"):
        return entry["account_id"] == me.account_id
    if entry.get("person_id"):
        return entry["person_id"] == me.person_id
    return bool(me.name) and norm(entry.get("name") or "") == norm(me.name) and not me.shared_name


def _named(intent: dict, slot: str, me: Me) -> bool:
    return any(_is_me(e, me) for e in _entries((intent.get("people") or {}).get(slot)))


def closer_slot(intent: dict) -> str | None:
    """The slot holding the named closer: sponsor, decider, owner (else reporter) or organiser, per type."""
    people = intent.get("people") or {}
    return next((s for s in _CLOSER_SLOT.get(intent.get("type"), ()) if _entries(people.get(s))), None)


def _live_share(entry: dict, now: datetime) -> bool:
    if not isinstance(entry, dict) or entry.get("revoked_at"):
        return False
    exp = entry.get("expires_at")
    if not exp:
        return True
    try:
        at = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
    except ValueError:
        return False  # fail closed
    return (at if at.tzinfo else at.replace(tzinfo=timezone.utc)) > now


def roles_of(intent: dict, me: Me, now: datetime | None = None) -> frozenset[str]:
    """The viewer's role set in this intent (rule 3). Empty: they may not know it exists (404)."""
    if "super_admin" in me.roles:  # ruling 5: existence through the kernel projection only, never through layer 2
        return frozenset()
    now = now or datetime.now(timezone.utc)
    roles: set[str] = set()
    if _named(intent, "organiser", me):
        roles.add("organiser")
    slot = closer_slot(intent)
    if slot and _named(intent, slot, me):
        roles.add("closer")
    if _named(intent, "participants", me) or _named(intent, "reporter", me):
        roles.add("participant")
    if _named(intent, "affected", me):
        roles.add("affected")
    if _named(intent, "observers", me):
        roles.add("observer")
    if me.areas & {norm(a) for a in intent.get("areas") or [] if isinstance(a, str)}:
        roles.add("area_member")
    if "company_admin" in me.roles:
        roles.add("company_admin")
    if any(_live_share(e, now) and _is_me(e, me) for e in (intent.get("share") or {}).get("who_may_open") or []):
        roles.add("share_visitor")
    if intent.get("state") == "draft":  # ruling 14: the creator and nobody else
        if not me.account_id or intent.get("created_by") != me.account_id:
            return frozenset()
        roles.add("creator")
    if roles & _CONTENT_ROLES or ("affected" in roles and intent.get("affected_may_read") is True):
        roles.add("content")
    return frozenset(roles)


def person_name(intent: dict, slot: str | None, plane: CompanyPlane | None = None) -> str | None:
    """The display name of the first person in a slot, from the entry or the profile; None when unresolvable."""
    entry = next(iter(_entries((intent.get("people") or {}).get(slot))), None) if slot else None
    if isinstance(entry, dict) and entry.get("name"):
        return str(entry["name"])
    pid = entry.get("person_id") if isinstance(entry, dict) else entry
    if plane is not None and isinstance(pid, str):
        cell = store.raw(plane)["people"].get(pid, {}).get("name")
        if isinstance(cell, dict) and cell.get("value"):
            return str(cell["value"])
    return None


def refusal(intent: dict, roles: frozenset[str], allowed: frozenset[str], code: str | None,
            plane: CompanyPlane | None = None) -> IntentRefused:
    """The right refusal for a viewer who has some role here but not one of `allowed`."""
    if code == "intent_not_your_close":
        who = person_name(intent, closer_slot(intent), plane)
        return IntentRefused(403, code, f"Only {who or 'the named closer'} can close this. North has told them it is waiting.")
    if "content" in allowed and "content" not in roles:
        who = person_name(intent, "organiser", plane)
        words = "You can see that this exists. You can open it if the organiser adds you." + (f" Organiser: {who}." if who else "")
        return IntentRefused(403, "intent_content_closed", words, **({"organiser": who} if who else {}))
    return IntentRefused(403, code or "intent_read_only", READ_ONLY)


def _log_refused(request: Request, intent_id, code: str) -> None:
    """The run log line of file 14: who, intent id, route, reason code. Never content."""
    log.info("intent_refused account=%s intent=%s route=%s %s code=%s", getattr(request.state, "account_id", None),
             intent_id, request.method, request.url.path, code)


def require_intent_role(request: Request, intent: dict, allowed, *, code: str | None = None,
                        plane: CompanyPlane | None = None, me: Me | None = None) -> frozenset[str]:
    """Layer 2 then layer 3. Returns the viewer's role set, or raises IntentRefused with file 14's code and words."""
    allowed = frozenset(allowed)
    plane = plane or _plane(request)
    roles = roles_of(intent, me or Me.of(request, plane))
    try:
        if not roles:
            raise IntentRefused(404, "intent_not_found", NOT_FOUND)
        granted = roles & allowed
        if request.method not in ("GET", "HEAD") and granted == {"content"} and not roles & _WRITERS:
            granted = frozenset()  # observers, share visitors and affected readers read the content, never write through it
        if not granted:
            raise refusal(intent, roles, allowed, code, plane)
        if request.method not in ("GET", "HEAD") and intent.get("state") in FROZEN:
            raise IntentRefused(409, "intent_closed", CLOSED)
    except IntentRefused as exc:
        _log_refused(request, intent.get("id"), exc.detail["error"])
        raise
    return roles


def load_intent(plane: CompanyPlane, intent_id: str) -> dict:
    """`intents/<id>/intent.json`, or IntentRefused: 404 for a bad or missing id, 500 for a file that cannot be read."""
    try:
        if not intent_id or "/" in intent_id:
            raise CrossCompanyError("bad id")
        intent = read_json_strict(plane.path("intents", intent_id, "intent.json"), dict)
    except CrossCompanyError:
        intent = None
    except (OSError, ValueError):
        raise IntentRefused(500, "intent_unreadable", UNREADABLE) from None
    if intent is None:
        raise IntentRefused(404, "intent_not_found", NOT_FOUND)
    return intent


@dataclass(frozen=True)
class IntentAccess:
    intent: dict
    roles: frozenset[str]
    plane: CompanyPlane


def intent_roles(allowed, *, code: str | None = None):
    """FastAPI dependency for a route with `{intent_id}`: loads the record and runs require_intent_role."""
    allowed = frozenset(allowed)

    def dependency(request: Request, intent_id: str) -> IntentAccess:
        try:
            plane = _plane(request)
        except PermissionError:
            raise IntentRefused(404, "intent_not_found", NOT_FOUND) from None
        intent = load_intent(plane, intent_id)
        return IntentAccess(intent, require_intent_role(request, intent, allowed, code=code, plane=plane), plane)
    return dependency
