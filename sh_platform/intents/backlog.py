"""IC v2 (21): the backlog, `intents/backlog.json` in the company plane. Open, merge, park, drop, bring back, "I feel this".

Nothing is deleted: every change is a status and a history line. Actors are the source intent's organiser and the company admin; the
area lead needs a `lead` cell on the profile's area record (21 open question 1), so until it exists the reminder goes to the admin.
`create_item(...)` is the one create function (links.create, the closure next row and the check-in fate call it).
"""
import re
import secrets
import statistics
import time
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from modules.m1_intent.domain.together import default_review_date  # the Future shelf's rule: today plus one quarter
from sh_platform.intents import _plane, _viewer
from sh_platform.intents import lifecycle as L
from sh_platform.intents import store as S
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile import view as pview

router = APIRouter()

KINDS = ("idea", "ops_problem", "request")
STATUSES = ("open", "parked", "became_intent", "merged", "dropped")
OPEN_TYPES = ("initiative", "brainstorm", "problem", "decision")  # a weekly check-in is never made from an item
SUGGEST = {"idea": "brainstorm", "ops_problem": "problem", "request": "initiative"}
REASON_CHARS = 300  # the Define form's reason limit (maxLength on the Future shelf input)
STATUS_ACTIONS = {"created", "parked", "dropped", "merged", "merged_in", "opened", "brought_back"}
NO_LEAD = "No lead named for {area}."
NOT_ACTOR = "Only the organiser of the source or the company admin can do that."


class Refused(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _file(plane):
    return plane.path("intents", "backlog.json")


def read_items(plane) -> list[dict]:
    try:
        doc = read_json_strict(_file(plane), dict) or {}
    except (OSError, ValueError):
        return []
    return [i for i in doc.get("items") or [] if isinstance(i, dict)]


def _today(plane) -> date:
    return datetime.now(L.company_zone(plane)).date()


def _mutate(plane, change):
    """Read, change, write under the backlog lock. `change(items)` returns what the caller gets back."""
    with lock_for(_file(plane)):
        try:
            doc = read_json_strict(_file(plane), dict) or {"items": []}
        except (OSError, ValueError):
            raise Refused(409, "The backlog could not be read. Please tell your administrator.") from None
        out = change(doc.setdefault("items", []))
        write_json_atomic(_file(plane), doc)
        return out


def _hist(item: dict, by: str, action: str, note: str = "") -> None:
    item["history"].append({"at": S.now_iso(), "by": by, "action": action, "note": note})


def _clean(text, limit: int = REASON_CHARS) -> str:
    return " ".join(str(text or "").split())[:limit]


def create_item(plane, *, title: str, kind: str, area: str | None, source: dict, raised_by: str, why: str = "", quote: str = "",
                review_date: str | None = None) -> dict:
    """North writes a new open item after the source closes. `raised_by` is an account id or "anonymous"; the raiser's tap counts first."""
    if kind not in KINDS or not _clean(title):
        raise ValueError("an item needs a title and a kind")
    now = S.now_iso()
    item = {"id": "bl-" + secrets.token_hex(8), "title": _clean(title, 200), "kind": kind, "area": area or None,
            "source": {k: source.get(k) for k in ("intent_id", "type", "stage_ref", "week_key", "week_item_id")},
            "raised_by": raised_by or "anonymous", "raised_at": now,
            "why_it_matters": {"text": _clean(why), "drafted_by": "north", "edited_by": None, "edited_at": None},
            "source_quote": "" if raised_by == "anonymous" else _clean(quote, 500),
            "taps": [] if raised_by == "anonymous" else [{"by": raised_by, "at": now}],
            "review_date": review_date or default_review_date(time.time()), "status": "open", "parked": None, "dropped": None,
            "merged_into": None, "merged_from": [], "opened_intent": None, "reminded_at": [], "history": []}
    _hist(item, "North", "created")
    return _mutate(plane, lambda items: (items.append(item), item)[1])


# ---- who sees and who acts ---------------------------------------------------------------------------------------------------

def _source(plane, item: dict) -> dict | None:
    try:
        return S.read_intent(plane, (item.get("source") or {}).get("intent_id") or "")
    except S.Unreadable:
        return None


def is_actor(plane, viewer: pview.Viewer, item: dict) -> bool:
    if pview.ADMIN in viewer.roles:
        return True
    src = _source(plane, item)
    return bool(src) and S._named((src.get("people") or {}).get("organiser"), viewer)


def may_see(plane, viewer: pview.Viewer, item: dict) -> bool:
    if pview.ADMIN in viewer.roles:
        return True
    if item.get("area") and pview.norm(item["area"]) in S.areas_of(plane, viewer):
        return True
    return is_actor(plane, viewer, item)


def in_area(plane, viewer: pview.Viewer, item: dict) -> bool:
    return bool(item.get("area")) and pview.norm(item["area"]) in S.areas_of(plane, viewer) or pview.ADMIN in viewer.roles


# ---- the reminder and the numbers --------------------------------------------------------------------------------------------

def reminder_line(item: dict) -> str:
    n = len(item.get("taps") or [])
    return f"Review: {item['title']}. {n} {'person feels' if n == 1 else 'people feel'} this. Open an intent, park it again, or drop it."


def remind_due(plane, today: date | None = None, *, peek: bool = False, only: set[str] | None = None) -> list[dict]:
    """North's review reminder: one Pulse line per item due (review date today or earlier, open or parked), then once a week.
    `peek` lists the due lines and writes nothing; `only` stamps just those item ids (the lines the page actually showed).
    Stamping writes `reminded_at` and a history line. No lead cell exists yet, so every line goes to the company admin with the no-lead note."""
    today = today or _today(plane)

    def is_due(it):
        if it["status"] not in ("open", "parked") or str(it.get("review_date") or "9999") > today.isoformat():
            return False
        last = max(it.get("reminded_at") or [""])
        return not (last and last[:10] > (today - timedelta(days=7)).isoformat())

    def line_of(it):
        return {"to": "company_admin", "text": reminder_line(it), "note": NO_LEAD.format(area=it.get("area") or "Company-wide"),
                "href": f"/centre/intent/backlog?item={it['id']}", "due": it.get("review_date"), "raiser": it.get("raised_by")}

    def change(items):
        lines = []
        for it in items:
            if not is_due(it) or (only is not None and it["id"] not in only):
                continue
            it.setdefault("reminded_at", []).append(today.isoformat())
            _hist(it, "North", "reminded", "Reminder sent to the company admin")
            lines.append(line_of(it))
        return lines
    items = read_items(plane)
    if peek:
        return [line_of(i) for i in items if is_due(i)]
    return _mutate(plane, change) if any(is_due(i) and (only is None or i["id"] in only) for i in items) else []  # the lock and the write only when a reminder is due


def counters(items: list[dict], today: date) -> list[dict]:
    """Per area (None is Company-wide): open, parked, due, oldest open age, median age (five or more), became intents and share."""
    out = []
    for area in sorted({i.get("area") or "" for i in items}):
        mine = [i for i in items if (i.get("area") or "") == area]
        open_ = [i for i in mine if i["status"] == "open"]
        ages = [(today - date.fromisoformat(i["raised_at"][:10])).days for i in open_]
        became = sum(i["status"] == "became_intent" for i in mine)
        out.append({"area": area or None, "open": len(open_), "parked": sum(i["status"] == "parked" for i in mine),
                    "due": sum(i["status"] in ("open", "parked") and str(i.get("review_date") or "9999") <= today.isoformat() for i in mine),
                    "oldest_days": max(ages) if ages else None,
                    "median_days": statistics.median(ages) if len(ages) >= 5 else "Fewer than five",
                    "became_intent": became, "became_share": f"{round(100 * became / len(mine))}%" if len(mine) >= 5 else "Fewer than five",
                    "dropped": sum(i["status"] == "dropped" for i in mine), "merged": sum(i["status"] == "merged" for i in mine)})
    return out


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", str(text).lower())}


def similar(items: list[dict], item: dict) -> dict | None:
    """North's "looks like the same thing": another open item in the same area sharing two or more longer words of title or line.
    ponytail: word overlap, not a judged reading; swap for North through the gateway if it misses too often."""
    if item["status"] != "open":
        return None
    dismissed = {h["note"] for h in item["history"] if h["action"] == "not_same"}
    mine = _words(item["title"] + " " + item["why_it_matters"]["text"])
    for o in items:
        if o["id"] != item["id"] and o["status"] == "open" and o.get("area") == item.get("area") and o["id"] not in dismissed \
                and len(mine & _words(o["title"] + " " + o["why_it_matters"]["text"])) >= 2:
            return {"id": o["id"], "title": o["title"]}
    return None


# ---- the actions -------------------------------------------------------------------------------------------------------------

def act(plane, viewer: pview.Viewer, item_id: str, action: str, body: dict) -> dict:
    """One press by a person. Returns the item (or {item, intent_id} for open)."""
    who = viewer.name or "Someone"
    found = next((i for i in read_items(plane) if i["id"] == item_id), None)
    if found is None or not may_see(plane, viewer, found):
        raise Refused(404, S.NOT_FOUND)
    if action == "tap":
        if not in_area(plane, viewer, found) or found["raised_by"] == viewer.account_id:
            raise Refused(403, "Only people in the item's area can say they feel this; your raise already counts.")
    elif not is_actor(plane, viewer, found):
        raise Refused(403, NOT_ACTOR)
    if action == "open":
        return _open(plane, viewer, found, body)

    def change(items):
        it = next(i for i in items if i["id"] == item_id)
        st = it["status"]
        if action == "tap":
            mine = [t for t in it["taps"] if t["by"] == viewer.account_id]
            it["taps"] = [t for t in it["taps"] if t["by"] != viewer.account_id] if mine else [*it["taps"], {"by": viewer.account_id, "at": S.now_iso()}]
        elif action in ("park", "drop"):
            reason = _clean(body.get("reason"))
            if not reason:
                raise Refused(400, "Please say why this is parked for later." if action == "park" else "Please say why this is dropped.")
            if st not in (("open",) if action == "park" else ("open", "parked")):
                raise Refused(409, "This item cannot move there from where it is now.")
            if action == "park":
                review = str(body.get("review_date") or default_review_date(time.time()))
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", review) or review <= _today(plane).isoformat():
                    raise Refused(400, "Pick a review date in the future.")
                it.update(status="parked", review_date=review, parked={"reason": reason, "by": who, "at": S.now_iso(), "review_date": review})
            else:
                it.update(status="dropped", dropped={"reason": reason, "by": who, "at": S.now_iso()})
            _hist(it, who, "parked" if action == "park" else "dropped", reason)
        elif action == "bring-back":
            if st not in ("parked", "dropped"):
                raise Refused(409, "Only a parked or dropped item can come back.")
            it["status"] = "open"
            if not it.get("review_date") or it["review_date"] <= _today(plane).isoformat():
                it["review_date"] = default_review_date(time.time())
            _hist(it, who, "brought_back")
        elif action == "merge":
            other = next((i for i in items if i["id"] == body.get("other")), None)
            if other is None or other["id"] == it["id"] or other["status"] != "open" or st != "open" or other.get("area") != it.get("area"):
                raise Refused(400, "No other open item in this area.")
            keep, gone = (it, other) if body.get("keep", "this") == "this" else (other, it)
            line = _clean(body.get("why")) or keep["why_it_matters"]["text"]
            seen = {t["by"] for t in keep["taps"]}
            keep["taps"] += [t for t in gone["taps"] if t["by"] not in seen]
            keep["review_date"] = min(keep["review_date"], gone["review_date"])
            keep["merged_from"] = [*keep["merged_from"], gone["id"], *gone["merged_from"]]
            keep["why_it_matters"].update(text=line, edited_by=who, edited_at=S.now_iso())
            gone.update(status="merged", merged_into=keep["id"])
            _hist(keep, who, "merged_in", gone["title"])
            _hist(gone, who, "merged", keep["title"])
            return keep
        elif action == "not-same":
            _hist(it, who, "not_same", str(body.get("other") or ""))
        elif action == "edit":
            if st not in ("open", "parked"):
                raise Refused(409, "Only an open or parked item can be edited.")
            for k in ("title", "kind", "area", "why", "review_date"):
                if k not in body:
                    continue
                v = body[k]
                if k == "title" and not _clean(v):
                    raise Refused(400, "A title is needed.")
                if k == "kind" and v not in KINDS or k == "review_date" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(v)):
                    raise Refused(400, "Please choose one of the values shown.")
                if k == "why":
                    it["why_it_matters"].update(text=_clean(v), edited_by=who, edited_at=S.now_iso())
                else:
                    it[k] = _clean(v, 200) if isinstance(v, str) else v
                _hist(it, who, "edited", k)
        else:
            raise Refused(404, S.NOT_FOUND)
        return it
    return _mutate(plane, change)


def _open(plane, viewer: pview.Viewer, item: dict, body: dict) -> dict:
    """"Open it": a draft only its opener sees, `links.from` the source intent, `backlog_ref` the item; the item becomes an intent."""
    from sh_platform.intents import links as K
    type_ = body.get("type") or SUGGEST[item["kind"]]
    if type_ not in OPEN_TYPES:
        raise Refused(400, "Choose an Initiative, Brainstorm, Problem or Decision.")
    if item["status"] not in ("open", "parked"):
        raise Refused(409, "This item cannot move there from where it is now.")
    title = _clean(body.get("title"), 200) or item["title"]
    areas = [a for a in body.get("areas") or ([item["area"]] if item.get("area") else []) if isinstance(a, str) and a.strip()]
    if not areas:
        raise Refused(400, "Name at least one area.")
    src = _source(plane, item)
    rec = L.new_record(type_, (src or {}).get("company") or "", L.person(viewer.account_id, viewer.name), S.now_iso(), title=title,
                       purpose=item["why_it_matters"]["text"], areas=areas, link_from=src["id"] if src else None)
    rec["start_answers"] = K.prefill({"id": (src or {}).get("id"), "type": "backlog", "title": "the backlog item", "areas": areas}, type_, title,
                                     item["id"], K.area_ids(plane), why="From the backlog item")
    rec["backlog_ref"] = item["id"]
    S.create_intent(plane, rec)
    if src:
        K.link_intents(plane, src["id"], rec["id"], type_, by=viewer)

    def change(items):
        it = next(i for i in items if i["id"] == item["id"])
        it.update(status="became_intent", opened_intent=rec["id"])
        _hist(it, viewer.name or "Someone", "opened", type_)
        return it
    return {"item": _mutate(plane, change), "intent_id": rec["id"], "href": f"/centre/intent/new?type={type_}&from={(src or {}).get('id') or ''}&draft={rec['id']}"}  # the start questions


# ---- what a viewer receives --------------------------------------------------------------------------------------------------

def _name(request: Request, account_id: str) -> str:
    if account_id == "anonymous":
        return "Anonymous"
    return str((request.app.state.account_store.get(account_id) or {}).get("display_name") or "Not recorded")


def view_item(request: Request, plane, viewer: pview.Viewer, it: dict, items: list[dict], full: bool = False) -> dict:
    actor = is_actor(plane, viewer, it)
    admin = pview.ADMIN in viewer.roles
    src = _source(plane, it)
    tier = S.tier_of(src, viewer, S.areas_of(plane, viewer)) if src else None
    out = {k: it[k] for k in ("id", "title", "kind", "area", "raised_at", "review_date", "status", "merged_into", "merged_from", "opened_intent")}
    out.update(raised_by=_name(request, it["raised_by"]), why_it_matters=it["why_it_matters"], taps=len(it["taps"]),
               tapped=any(t["by"] == viewer.account_id for t in it["taps"]),
               can_tap=in_area(plane, viewer, it) and it["raised_by"] != viewer.account_id and it["status"] in ("open", "parked"),
               actor=actor, reason=(it.get(it["status"]) or {}).get("reason") if it["status"] in ("parked", "dropped") else None,
               source={"intent_id": src["id"], "title": src["title"], "type": src["type"], "closed_at": (src.get("closure") or {}).get("closed_at"),
                       "week_key": it["source"].get("week_key"), "may_open": tier == "content"} if tier else None)
    if full:
        out["source_quote"] = it["source_quote"] if tier == "content" else None
        out["tap_names"] = [_name(request, t["by"]) for t in it["taps"]] if actor or admin else None
        out["history"] = [h for h in it["history"] if actor or admin or h["action"] in STATUS_ACTIONS]
        names = {i["id"]: i["title"] for i in items}
        out["related"] = [{"id": i, "title": names.get(i, "")} for i in it["merged_from"]]
        out["similar"] = similar(items, it) if actor else None
        out["merge_choices"] = [{"id": i["id"], "title": i["title"]} for i in items
                                if i["id"] != it["id"] and i["status"] == "open" and i.get("area") == it.get("area")] if actor else []
        out["suggest_type"] = SUGGEST[it["kind"]]
        out["default_review"] = default_review_date(time.time())
    return out


def _fail(e: Refused) -> JSONResponse:
    return JSONResponse({"message": e.message}, status_code=e.status)


@router.get("/api/intents/backlog")
def get_intents_backlog(request: Request):
    plane, viewer = _plane(request), _viewer(request)
    q = request.query_params
    items, today = read_items(plane), _today(plane)
    seen = [i for i in items if may_see(plane, viewer, i)]
    admin = pview.ADMIN in viewer.roles
    area, status = q.get("area"), q.get("status") or "open"
    kinds = [k for k in (q.get("kind") or "").split(",") if k in KINDS]
    in_area_ = [i for i in seen if area is None or (i.get("area") or "") == ("" if area == "company" else area)]
    shown = [i for i in in_area_ if i["status"] == status and (not kinds or i["kind"] in kinds)
             and (q.get("due") != "1" or str(i.get("review_date") or "9999") <= today.isoformat())]
    shown.sort(key=lambda i: i.get("review_date") or "9999")
    mine = S.areas_of(plane, viewer)
    leadish = admin or any(is_actor(plane, viewer, i) for i in seen)
    return {"items": [view_item(request, plane, viewer, i, items) for i in shown],
            "areas": [{"area": a or None, "open": sum(i["status"] == "open" and (i.get("area") or "") == a for i in seen)}
                      for a in sorted({i.get("area") or "" for i in seen} | ({""} if admin else set()))],
            "kinds": {k: sum(i["kind"] == k for i in in_area_ if i["status"] == status) for k in KINDS},
            "due": sum(i["status"] in ("open", "parked") and str(i.get("review_date") or "9999") <= today.isoformat() for i in in_area_),
            "counters": counters(seen, today) if leadish else [{"area": c["area"], "open": c["open"]} for c in counters(seen, today)],
            "leadish": leadish, "tagged": bool(mine) or admin, "any": bool(seen), "lead_note": "Not available yet: no area lead is named.",
            # mirrors route_permissions GET /api/intents/opportunities, so the page never asks for what it would be refused
            "opportunities": any(r in viewer.roles for r in ("owner", "company_admin", "sponsor", "analyst"))}


@router.get("/api/intents/backlog/{item_id}")
def get_intents_backlog_by_item_id(item_id: str, request: Request):
    plane, viewer = _plane(request), _viewer(request)
    items = read_items(plane)
    it = next((i for i in items if i["id"] == item_id), None)
    if it is None or not may_see(plane, viewer, it):
        return JSONResponse({"message": S.NOT_FOUND}, status_code=404)
    return view_item(request, plane, viewer, it, items, full=True)


async def _body(request: Request) -> dict:
    try:
        b = await request.json()
    except ValueError:
        return {}
    return b if isinstance(b, dict) else {}


@router.patch("/api/intents/backlog/{item_id}")
async def patch_intents_backlog_by_item_id(item_id: str, request: Request):
    try:
        return act(_plane(request), _viewer(request), item_id, "edit", await _body(request))
    except Refused as e:
        return _fail(e)


@router.post("/api/intents/backlog/{item_id}/{action}")
async def post_intents_backlog_by_item_id_by_act(item_id: str, action: str, request: Request):
    try:
        return act(_plane(request), _viewer(request), item_id, action, await _body(request))
    except Refused as e:
        return _fail(e)
