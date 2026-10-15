"""Areas and visibility (spec 05): who learns an intent exists and what they may open, by one table applied in one place.

`read_intent(plane, intent, viewer)` is the only function that decides it. B01's store, every list, every Pulse line and every content route
call it (or `may_open_content`); no screen or route decides visibility for itself. The matrix below is typed out as a literal, row by row,
exactly as file 05 section "Rules" prints it. A viewer holds many relations on an intent; each column takes the most generous cell among the
rows those relations earn (union). A viewer with no relation, and anyone but the starter on a draft, gets None: the caller answers 404.
Sealed and anonymous cards stay with `profile.view._cards`; the S and A cells only say whether the viewer reaches that rule at all.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.context_docs.api import _json_body, _plain
from sh_platform.intents import _plane, _viewer
from sh_platform.jsonfile import read_json_strict
from sh_platform.profile import areas as areas_store, store
from sh_platform.profile.view import ADMIN, Viewer, norm

router = APIRouter()
NOT_FOUND = "We could not find that."
SUPER_ADMIN = "super_admin"
COLUMNS = ("existence", "title", "stage_clock", "people", "content", "sealed", "anonymous", "outcome", "closure", "ratings")

# Y yes, N no. people: all | speakers (organiser, sponsor; the module adds who spoke) | organiser | organiser_counts | count | N.
# outcome: Y | closed (once the state is closed) | N. closure: Y | came_next (`what_came_out`, `next`) | came_next_closed | N.
# ratings: Y (anonymous without name) | count_avg3 (count; average from three) | N. sealed S, anonymous A: see profile.view._cards.
# title: Y | unless_private (super admin; the company switch hides it). stage_clock: Y | state_dates_box (state, dates, time box status).
_C = COLUMNS
MATRIX: dict[str, dict[str, str]] = {
    row: dict(zip(_C, cells)) for row, cells in {
        "organiser":     ("Y", "Y", "Y", "all",              "Y", "S", "A", "Y",      "Y",                 "Y"),
        "sponsor":       ("Y", "Y", "Y", "all",              "Y", "S", "A", "Y",      "Y",                 "Y"),
        "participant":   ("Y", "Y", "Y", "all",              "Y", "S", "A", "Y",      "Y",                 "Y"),
        "observer":      ("Y", "Y", "Y", "all",              "Y", "S", "A", "Y",      "Y",                 "Y"),
        "affected_off":  ("Y", "Y", "Y", "all",              "N", "N", "N", "closed", "came_next_closed",  "N"),
        "affected_on":   ("Y", "Y", "Y", "all",              "Y", "S", "A", "Y",      "Y",                 "Y"),
        "same_area":     ("Y", "Y", "Y", "organiser",        "N", "N", "N", "closed", "came_next_closed",  "N"),
        "other_area":    ("N", "N", "N", "N",                "N", "N", "N", "N",      "N",                 "N"),
        "company_admin": ("Y", "Y", "Y", "organiser_counts", "N", "N", "N", "Y",      "came_next",         "count_avg3"),
        "super_admin":   ("Y", "unless_private", "state_dates_box", "count", "N", "N", "N", "N", "N",       "N"),
        "share_visitor": ("Y", "Y", "Y", "speakers",         "Y", "S", "A", "Y",      "Y",                 "N"),
    }.items()
}
_RANK = {  # least to most generous, per column; the union takes the highest
    "title": ("N", "unless_private", "Y"), "stage_clock": ("N", "state_dates_box", "Y"),
    "people": ("N", "count", "organiser_counts", "organiser", "speakers", "all"),
    "outcome": ("N", "closed", "Y"), "closure": ("N", "came_next_closed", "came_next", "Y"), "ratings": ("N", "count_avg3", "Y"),
}
SLOTS = ("sponsor", "decider", "owner", "reporter")
LISTS = ("participants", "advisers", "affected", "observers")
CONTENT_KEYS = ("refs", "start_answers", "links", "history", "event_count", "events", "catalogue_version", "version", "updated_at")


@dataclass(frozen=True)
class Context:
    """What the viewer's own profile says: areas by the account link, person id to account id, and the company's titles switch."""
    areas: frozenset[str] = frozenset()
    person_accounts: dict[str, str] = field(default_factory=dict)
    titles_private: bool = False
    area_names: frozenset[str] = frozenset()  # the same areas by name (normalised): records written by name still match a tag


def context_for(plane, viewer: Viewer) -> Context:
    """Read once per request and pass to `read_intent(..., ctx=)` when filtering a list."""
    doc = store.load(plane)
    accounts = {pid: areas_store._v(p, "account_id") for pid, p in doc["people"].items()}
    mine = areas_store.areas_of_account(doc, viewer.account_id)
    names = frozenset(norm(a["name"]) for a in areas_store.listing(doc) if a["id"] in mine and a["name"])
    return Context(mine, {k: v for k, v in accounts.items() if isinstance(v, str)}, areas_store.titles_private(doc), names)


def _name(p: Any) -> str:
    return str(p.get("name") or "") if isinstance(p, dict) else str(p or "")


def _is(person: Any, viewer: Viewer) -> bool:
    """A person object is {account_id, name}. Bound to an account: match the account. A guest: match the display name, unless two
    accounts share it (the same rule as profile.view)."""
    if not person:
        return False
    acct = person.get("account_id") if isinstance(person, dict) else None
    if acct:
        return bool(viewer.account_id) and acct == viewer.account_id
    return bool(viewer.name) and norm(_name(person)) == norm(viewer.name) and not viewer.shared_name


def _shared_with(intent: dict, viewer: Viewer, ctx: Context) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    mine = {norm(a) for a in ctx.areas} | ctx.area_names
    for e in (intent.get("share") or {}).get("entries") or []:  # share.py rows: person, area (link holders are admitted by the visitor route)
        if not isinstance(e, dict) or e.get("state", "live") != "live" or (e.get("expires_at") and str(e["expires_at"]) <= now):
            continue
        t = str(e.get("target") or "")
        if e.get("kind") == "area" and norm(t) in mine:
            return True
        if e.get("kind") == "person" and t and (t == viewer.account_id or ctx.person_accounts.get(t) == viewer.account_id and viewer.account_id):
            return True
    for e in (intent.get("share") or {}).get("who_may_open") or []:
        if isinstance(e, str):
            e = {"account_id": e}
        if e.get("revoked_at") or (e.get("expires_at") and str(e["expires_at"]) <= now):
            continue
        acct = e.get("account_id") or ctx.person_accounts.get(str(e.get("person_id") or ""))
        if acct and viewer.account_id and acct == viewer.account_id or not acct and not e.get("person_id") and _is(e, viewer):
            return True
    return False


def rows_for(intent: dict, viewer: Viewer, ctx: Context) -> list[str]:
    """The matrix rows this viewer earns on this intent. A draft: its starter only (ruling 14), nobody else, the admins included."""
    mine = bool(viewer.account_id) and viewer.account_id == intent.get("created_by")
    if intent.get("state") == "draft":
        return ["organiser"] if mine else []
    p = intent.get("people") or {}
    rows = []
    if mine or _is(p.get("organiser"), viewer):
        rows.append("organiser")
    if _is(p.get("sponsor"), viewer):
        rows.append("sponsor")
    if any(_is(p.get(k), viewer) for k in ("decider", "owner", "reporter")) or any(_is(x, viewer) for k in ("participants", "advisers") for x in p.get(k) or []):
        rows.append("participant")
    if any(_is(x, viewer) for x in p.get("observers") or []):
        rows.append("observer")
    if any(_is(x, viewer) for x in p.get("affected") or []):
        rows.append("affected_on" if intent.get("affected_may_read") is True else "affected_off")
    if ({norm(a) for a in ctx.areas} | ctx.area_names) & {norm(a) for a in intent.get("areas") or [] if isinstance(a, str)}:
        rows.append("same_area")
    if ADMIN in viewer.roles:
        rows.append("company_admin")
    if SUPER_ADMIN in viewer.roles:
        rows.append("super_admin")
    if _shared_with(intent, viewer, ctx):
        rows.append("share_visitor")
    return rows


def columns_for(plane, intent: dict, viewer: Viewer, ctx: Context | None = None) -> dict[str, str] | None:
    """The ten matrix cells for this viewer and intent (union of the rows earned), or None: the intent is absent for them."""
    ctx = ctx or context_for(plane, viewer)
    rows = rows_for(intent, viewer, ctx)
    if not rows:
        return None
    out = {}
    for col in COLUMNS:
        cells = [MATRIX[r][col] for r in rows]
        out[col] = max(cells, key=_RANK[col].index) if col in _RANK else next((c for c in cells if c != "N"), "N")
    return out


def may_open_content(plane, intent: dict, viewer: Viewer, ctx: Context | None = None) -> bool:
    """Every module route that serves an intent's walls, charters, baselines or assessments calls this before answering."""
    cols = columns_for(plane, intent, viewer, ctx)
    return bool(cols) and cols["content"] == "Y"


def _count(p: dict) -> int:
    people = [p.get(k) for k in ("organiser",) + SLOTS if p.get(k)] + [x for k in LISTS for x in p.get(k) or []]
    return len({(x.get("account_id") or norm(_name(x))) if isinstance(x, dict) else norm(x) for x in people})


def _status(intent: dict) -> str:
    box, now = intent.get("time_box") or {}, datetime.now(timezone.utc).isoformat()
    if not box.get("starts"):
        return "not_started"
    return "not_started" if str(box["starts"]) > now else "ended" if box.get("ends") and str(box["ends"]) < now else "running"


def read_intent(plane, intent: dict, viewer: Viewer, ctx: Context | None = None) -> dict | None:
    """The intent as this viewer may see it, or None (answer 404, never 403). Account ids and `rated_by` never leave. Worked out at read time
    from the record and the viewer, never stored per person."""
    ctx = ctx or context_for(plane, viewer)
    c = columns_for(plane, intent, viewer, ctx)
    if c is None:
        return None
    p, closed = intent.get("people") or {}, intent.get("state") == "closed"
    out: dict[str, Any] = {"id": intent.get("id"), "type": intent.get("type"), "state": intent.get("state"), "areas": list(intent.get("areas") or [])}
    if c["title"] == "Y" or (c["title"] == "unless_private" and not ctx.titles_private):
        out["title"] = intent.get("title")
    if c["title"] == "Y":
        out["purpose"] = intent.get("purpose")
    if intent.get("state") == "cancelled" and c["title"] == "Y":
        out["cancel_reason"] = (intent.get("closure") or {}).get("cancel_reason")
    if c["stage_clock"] == "Y":
        out["stages"] = [{"key": s.get("key"), "state": s.get("state")} for s in intent.get("stages") or []]
        out["time_box"] = intent.get("time_box")
    else:
        out["time_box"] = {k: (intent.get("time_box") or {}).get(k) for k in ("starts", "ends")}
        out["time_box_status"] = _status(intent)
    ppl = c["people"]
    out["people_count"] = _count(p)
    if ppl != "N" and ppl != "count":
        names = {"organiser": {"name": _name(p.get("organiser"))}}
        if ppl in ("all", "speakers"):
            names["sponsor"] = {"name": _name(p.get("sponsor"))} if p.get("sponsor") else None
        if ppl == "all":
            names.update({k: ({"name": _name(p[k])} if p.get(k) else None) for k in ("decider", "owner", "reporter")})
            names.update({k: [{"name": _name(x)} for x in p.get(k) or []] for k in LISTS})
        if ppl == "organiser_counts":
            names["counts"] = {k: len(p.get(k) or []) for k in ("participants", "affected", "observers")}
        out["people"] = names
    if c["outcome"] == "Y" or c["outcome"] == "closed" and closed:
        out["outcome"] = intent.get("outcome")
    cl = intent.get("closure") or {}
    if c["closure"] == "Y":
        out["closure"] = {k: v for k, v in cl.items() if k != "cancel_reason" or c["title"] == "Y"}
    elif c["closure"] == "came_next" or c["closure"] == "came_next_closed" and closed:
        out["closure"] = {"what_came_out": cl.get("what_came_out"), "next": cl.get("next")}
    rated = [{k: v for k, v in r.items() if k != "by"} for r in intent.get("ratings") or []]  # no author on any rating, ever
    if c["ratings"] == "Y":
        out["ratings"] = rated
    elif c["ratings"] == "count_avg3":
        n = len(rated)
        out["ratings"] = {"count": n, "average": round(sum(r.get("score", 0) for r in rated) / n, 1) if n >= 3 else None}
    if c["content"] == "Y":
        out.update({k: intent[k] for k in CONTENT_KEYS if k in intent})
    out["access"] = {"content": c["content"] == "Y", "sealed": c["sealed"] == "S", "anonymous": c["anonymous"] == "A"}
    return out


# ---- routes: the area lists for every company role; the admin routes for the company admin (also checked here) ----

def _not_found() -> JSONResponse:
    return _plain(404, "not_found", NOT_FOUND)


def _admin(request: Request) -> bool:
    return ADMIN in (request.state.roles or [])


def _guard(request: Request, work):
    """Runs `work(plane, doc_by_name)` for the company admin; refusals and the single 403 answer in plain words."""
    if not _admin(request):
        return _plain(403, "forbidden", "Only the company admin can change areas.")
    try:
        return work(_plane(request))
    except areas_store.AreaRefusal as e:
        return _plain(e.status, "refused", str(e))
    except PermissionError:
        return _plain(403, "forbidden", "Your company space could not be opened. Please ask your administrator.")


def _by(request: Request) -> str:
    return str((request.app.state.account_store.get(request.state.account_id) or {}).get("display_name") or "Company admin")


def _pack(request: Request):
    rec = request.app.state.entitlements.company(request.state.company_id) or {}
    return request.app.state.packs.load(str(rec.get("industry") or "-"))


def _public(a: dict) -> dict:
    return {k: a[k] for k in ("id", "name", "kind", "status")}


@router.get("/api/company/areas")
def get_company_areas(request: Request):
    doc = store.load(_plane(request))
    out = {"areas": [_public(a) for a in areas_store.listing(doc)], "people_file": bool(doc["people"])}
    if _admin(request):
        out["titles_private"] = areas_store.titles_private(doc)
    return out


@router.get("/api/intents/areas")
def get_intents_areas(request: Request, pick: str = ""):
    """Active areas to pick from, this viewer's own areas, and (with `pick=a,b`) how many accounts that pick reaches."""
    plane = _plane(request)
    doc = store.load(plane)
    out = {"areas": [_public(a) for a in areas_store.listing(doc) if a["status"] == "active"],
           "mine": sorted(areas_store.areas_of_account(doc, request.state.account_id)), "can_set_up": _admin(request)}
    if pick:
        out["reach"] = areas_store.reach(doc, [i for i in pick.split(",") if i])
    return out


@router.get("/api/profile/areas/suggestions")
def get_area_suggestions(request: Request):
    def work(plane):
        doc = store.load(plane)
        pack = _pack(request)
        left = areas_store.suggestions(pack, doc)
        return {"suggested": left, "label": pack.suggestion_label, "lens": areas_store.lens_lines(doc),
                "all_taken": not left and bool(areas_store.suggestions(pack, {}))}
    return _guard(request, work)


@router.post("/api/profile/areas")
async def post_area(request: Request):
    body = await _json_body(request, 4096)
    if isinstance(body, JSONResponse):
        return body
    return _guard(request, lambda plane: {"id": areas_store.add(plane, body.get("name"), body.get("kind"), _by(request))})


@router.post("/api/profile/areas/accept")
async def post_area_accept(request: Request):
    body = await _json_body(request, 4096)
    if isinstance(body, JSONResponse):
        return body
    return _guard(request, lambda plane: {"ids": areas_store.accept(plane, _pack(request), body.get("ids"), _by(request))})


@router.post("/api/profile/areas/teams")
async def post_area_teams(request: Request):
    body = await _json_body(request, 4096)
    if isinstance(body, JSONResponse):
        return body
    return _guard(request, lambda plane: {"ids": areas_store.add_teams(plane, body.get("teams"), _by(request))})


@router.put("/api/profile/areas/settings")
async def put_area_settings(request: Request):
    body = await _json_body(request, 1024)
    if isinstance(body, JSONResponse):
        return body
    if not isinstance(body.get("titles_private"), bool):
        return _plain(400, "bad_request", "Choose on or off.")
    return _guard(request, lambda plane: areas_store.set_titles_private(plane, body["titles_private"], _by(request)) or {"ok": True})


@router.put("/api/profile/areas/{area_id}")
async def put_area(request: Request, area_id: str):
    body = await _json_body(request, 4096)
    if isinstance(body, JSONResponse):
        return body
    return _guard(request, lambda plane: areas_store.rename(plane, area_id, body.get("name"), _by(request)) or {"ok": True})


@router.post("/api/profile/areas/{area_id}/retire")
def post_area_retire(request: Request, area_id: str):
    return _guard(request, lambda plane: areas_store.set_status(plane, area_id, "retired", _by(request)) or {"ok": True})


@router.post("/api/profile/areas/{area_id}/restore")
def post_area_restore(request: Request, area_id: str):
    return _guard(request, lambda plane: areas_store.set_status(plane, area_id, "active", _by(request)) or {"ok": True})


@router.put("/api/profile/people/{pid}/areas")
async def put_person_areas(request: Request, pid: str):
    body = await _json_body(request, 4096)
    if isinstance(body, JSONResponse):
        return body
    return _guard(request, lambda plane: areas_store.tag(plane, pid, body.get("areas"), _by(request)) or {"ok": True})


_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")


def load_intent(plane, intent_id: str) -> dict | None:
    """The stored record, for the routes that have only an id. None when there is no such intent or the file cannot be read."""
    if not _ID.fullmatch(intent_id):
        return None
    try:
        doc = read_json_strict(plane.path("intents", intent_id, "intent.json"), dict)
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


@router.get("/api/intents/{intent_id}/content")
def get_intents_by_intent_id_content(request: Request, intent_id: str):
    """The intent as this viewer may read it. Hidden and missing answer the same 404; a viewer who may see it exists but not open it
    gets `access.content` false and the locked note on the screen."""
    from sh_platform.intents import store as S  # lazy: the store imports this module
    plane, viewer = _plane(request), _viewer(request)
    intent = load_intent(plane, intent_id)
    if not intent:
        return _not_found()
    ctx = S.context(plane, viewer)  # same deciders as the record route: company-wide token, named in records, share rows
    cols, view = S.columns(intent, viewer, ctx, plane)
    seen = read_intent(plane, view, viewer, ctx) if cols else None
    return S.mask_accounts(seen, viewer, {a: p for p, a in ctx.person_accounts.items()}) if seen is not None else _not_found()  # SEC0 #4
