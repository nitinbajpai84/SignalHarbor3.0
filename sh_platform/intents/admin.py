"""Admin views (spec 48): the company admin's All intents, counters, register and cancel, the centre settings, and the super admin's
existence view in Control.

One projection per viewer: `visibility.read_intent` with a viewer that holds only the admin row (or only the super admin row) decides
what leaves; nothing here reads a rating author, a note, a card or a share token. Settings: the title switch stays where file 05 keeps
it (`profile.areas`), the time boxes and the rest sit in `settings/intent_types.json` and `settings/intent_centre.json`.
Other cards import `read_settings(plane)`.
"""
import logging
import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from sh_platform.agents.runs import RunRegistry
from sh_platform.intents import clock as ck
from sh_platform.intents import events
from sh_platform.intents import measures
from sh_platform.intents import store as S
from sh_platform.intents import visibility as vis
from sh_platform.intents.types import load_catalogue
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CrossCompanyError, PlaneStore, valid_company_id
from sh_platform.profile import areas as areas_store
from sh_platform.profile import store as profile_store
from sh_platform.profile.view import ADMIN, Viewer

log = logging.getLogger(__name__)
router = APIRouter()

TIMED = ("initiative", "brainstorm", "problem", "decision")
OPEN = ("open", "in_session", "closing")
OPPORTUNITY_KEYS = ("drift_periods", "late_same_weekday", "checkin_items_same_step", "window_days", "theme_min_voices", "counter_periods", "min_periods_for_pattern")  # 56; 57 C4
CONFIDENCE = ("unlikely", "not_sure", "fairly_sure")  # 57 C4: min_confidence_to_show, the radar RANK keys
SCAN = ("on_read", "daily")  # 57 C5
DAYS = ("mon", "tue", "wed", "thu", "fri")  # 58 C13  # file 56, open question 1: no value invented
CSV_COLUMNS = ["id", "type", "title", "state", "areas", "organiser", "sponsor", "opened", "time_box_end", "closed_at", "closed_in_time",
               "extensions", "summary", "what_came_out", "next", "rating_count", "rating_mean", "cancelled_by", "cancel_reason"]
OFF = "The Intent centre is switched off for your company. Ask the platform operator."
SEE_ONLY = "You can see this but not change it."
PAGE = 50
_ADMIN_VIEWER = Viewer("", frozenset({ADMIN}), False, None)  # only the admin row of the matrix
_SUPER_VIEWER = Viewer("", frozenset({vis.SUPER_ADMIN}), False, None)


def _fail(status: int, message: str) -> JSONResponse:
    return JSONResponse({"message": message}, status_code=status)


# ---- settings ---------------------------------------------------------------------------------------------------------------

def _files(plane):
    return plane.path("settings", "intent_types.json"), plane.path("settings", "intent_centre.json")


def _read(path) -> dict:
    try:
        return read_json_strict(path, dict) or {}
    except (OSError, ValueError):
        return {}


def read_settings(plane) -> dict:
    """The company's centre settings, defaults filled in. Others read this and never the files:
    time_box_days {type: working days now in force}, time_box_overrides {type: days the company set}, titles_private,
    affected_default (False: the organiser chooses), opportunity {drift_periods, late_same_weekday, checkin_items_same_step, window_days}
    each None until the company sets it."""
    types_file, centre_file = _files(plane)
    over = {}
    for t, v in (_read(types_file).get("types") or {}).items():
        days = v.get("time_box_days") if isinstance(v, dict) else None
        if t in TIMED and _whole(days):
            over[t] = days
    cat = load_catalogue()["types"]
    centre = _read(centre_file)
    opp = centre.get("opportunity") if isinstance(centre.get("opportunity"), dict) else {}
    return {"time_box_days": {t: over.get(t, cat[t]["time_box_days"]) for t in cat}, "time_box_overrides": over,
            "titles_private": areas_store.titles_private(profile_store.load(plane)),
            "affected_default": centre.get("affected_default") is True,
            "opportunity": {**{k: opp[k] if _whole(opp.get(k)) else None for k in OPPORTUNITY_KEYS},
                            "scan": opp.get("scan") if opp.get("scan") in SCAN else None,
                            "min_confidence_to_show": opp.get("min_confidence_to_show") if opp.get("min_confidence_to_show") in CONFIDENCE else None},
            "proving": _proving_rules(plane)}


def _proving_rules(plane) -> dict:
    try:
        from sh_platform.intents import proving  # lazy: proving imports admin's neighbours
        return proving.rules(plane)
    except Exception:  # noqa: BLE001 - settings must read without Proving
        return {}


def _settings_view(plane) -> dict:
    s, cat = read_settings(plane), load_catalogue()["types"]
    return {**s, "time_boxes": {t: {"title": cat[t]["title"], "days": s["time_box_days"][t], "catalogue": cat[t]["time_box_days"],
                                    "changed": t in s["time_box_overrides"],
                                    "stages_total": sum(x["default_days"] for x in cat[t].get("stages") or [])} for t in TIMED}}


def _whole(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 1


def _save_settings(plane, body: dict, by: str) -> None:
    boxes, opp, prv = body.get("time_boxes") or {}, dict(body.get("opportunity") or {}), body.get("proving") or {}
    scan = opp.pop("scan", None) if isinstance(opp, dict) else None
    conf = opp.pop("min_confidence_to_show", None) if isinstance(opp, dict) else None
    if (not isinstance(boxes, dict) or not isinstance(opp, dict) or set(boxes) - set(TIMED) or set(opp) - set(OPPORTUNITY_KEYS)
            or not isinstance(prv, dict) or set(prv) - {"proving_min_periods", "report_day"}
            or (scan is not None and scan not in SCAN) or (conf is not None and conf not in CONFIDENCE) or prv.get("report_day") not in (None, *DAYS)
            or any(v is not None and not _whole(v) for v in [*boxes.values(), *opp.values(), prv.get("proving_min_periods")])
            or any(k in body and not isinstance(body[k], bool) for k in ("titles_private", "affected_default"))):
        raise ValueError("Time boxes are whole numbers of one or more working days. Check the values and try again.")
    types_file, centre_file = _files(plane)
    with lock_for(types_file.parent):
        doc = _read(types_file)
        types = {t: dict(v) for t, v in (doc.get("types") or {}).items() if isinstance(v, dict)}
        for t, v in boxes.items():
            if v is None:
                types.pop(t, None)
            else:
                types[t] = {"time_box_days": v}
        write_json_atomic(types_file, {"types": types})
        centre = _read(centre_file)
        if "affected_default" in body:
            centre["affected_default"] = body["affected_default"]
        centre["opportunity"] = {**{k: None for k in OPPORTUNITY_KEYS}, **(centre.get("opportunity") or {}), **opp,
                                 **({"scan": scan} if scan is not None else {}),
                                 **({"min_confidence_to_show": conf} if conf is not None else {})}
        if prv:
            centre["proving"] = {**(centre.get("proving") or {}), **prv}
        write_json_atomic(centre_file, centre)
    if "titles_private" in body:
        areas_store.set_titles_private(plane, body["titles_private"], by)


def _admin_only(request: Request) -> JSONResponse | None:
    return None if ADMIN in (request.state.roles or []) else _fail(403, SEE_ONLY)


def _by(request: Request) -> str:
    return str((request.app.state.account_store.get(request.state.account_id) or {}).get("display_name") or "Company admin")


def _log(plane, what: str, rows: int = 0) -> None:
    """One run-log line: that it happened, when, and a count. Never row text."""
    at = S.now_iso()
    RunRegistry(plane).record(agent="admin", module_id="m1_intent", started=at, finished=at, status="done", steps=rows,
                              tools_called=[what], numbers_replaced=0)


def _guard(request: Request):
    """The company admin only; the plane. Returns (plane, None) or (None, response)."""
    if (r := _admin_only(request)) is not None:
        return None, r
    try:
        plane = vis._plane(request)
    except PermissionError:
        return None, _fail(403, "Your company space could not be opened. Please ask your administrator.")
    if request.app.state.entitlements.switches(request.state.company_id)["centres"].get("intent") is False:
        return None, _fail(403, OFF)
    return plane, None


@router.get("/api/intents/settings")
def get_intents_settings(request: Request):
    """The centre settings. `?view=list|counters|register` answers the same admin reads as the three /admin routes: the
    permission table names this path, so the screen falls back to it until the /admin lines are added."""
    plane, bad = _guard(request)
    if bad:
        return bad
    view = request.query_params.get("view")
    if view in _VIEWS:
        return _VIEWS[view](request, plane)
    return _settings_view(plane)


@router.put("/api/intents/settings")
def put_intents_settings(body: dict, request: Request):
    plane, bad = _guard(request)
    if bad:
        return bad
    try:
        _save_settings(plane, body, _by(request))
    except ValueError as e:
        return _fail(400, str(e))
    _log(plane, "settings_saved")
    return _settings_view(plane)


# ---- the admin projection ---------------------------------------------------------------------------------------------------

def _tz(plane):
    name = ck._tz(plane)
    try:
        return ZoneInfo(name)
    except (KeyError, ValueError, OSError):  # no zone database on this machine: UTC
        return timezone.utc


def _local(text: str | None, tz, fmt: str = "%Y-%m-%d") -> str:
    try:
        return ck.parse(text).astimezone(tz).strftime(fmt) if text else ""
    except ValueError:
        return ""


def _person(ref, accounts) -> str:
    if isinstance(ref, dict):
        return str(ref.get("name") or "")
    acct = accounts.get(ref) if isinstance(ref, str) else None
    return str((acct or {}).get("display_name") or "")  # never the account id


def _days(a: datetime, b: datetime) -> int:
    return max(1, math.ceil(ck.working_days_between(a, b)))


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _chip(rec: dict, now: datetime) -> tuple[str, str]:
    """(key, words) of the spec 07 clock chip, worked out from the dates."""
    tb, state = rec.get("time_box") or {}, rec["state"]
    if state == "cancelled" or not (tb.get("starts") and tb.get("ends")):
        return "none", "Cancelled" if state == "cancelled" else "No clock yet"
    starts, ends = ck.parse(tb["starts"]), ck.parse(tb["ends"])
    if state == "closed":
        done = (rec.get("closure") or {}).get("closed_at")
        if not done:
            return "none", "No clock yet"
        late = ck.parse(done) > ends and ck.working_seconds(ends, ck.parse(done)) > 0
        return ("late", f"Done {_plural(_days(ends, ck.parse(done)), 'day', 'days')} late") if late else ("done", "Done in time")
    box = ck.clock(starts, ends, now)
    if box["state"] == "overdue":
        return "overdue", ck.overdue_words(-box["hours_left"])
    if box["state"] == "not_started":
        return "not_started", "Not started"
    return box["state"], ck.left_words(box)


def _first_line(text) -> str:
    return next((ln.strip() for ln in str(text or "").splitlines() if ln.strip()), "")


def _fallback_title(rec: dict, tz) -> str:
    """A seed intent with no title reads "<Type>, started <date>", never a blank cell."""
    when = _local((rec.get("time_box") or {}).get("starts") or rec.get("created_at"), tz, "%d %b %Y")
    name = (load_catalogue()["types"].get(rec["type"]) or {}).get("title") or str(rec["type"]).capitalize()
    return f"{name}, started {when}" if when else name


def _cut(plane, rec: dict) -> dict | None:
    return vis.read_intent(plane, rec, _ADMIN_VIEWER, vis.Context())


def _row(plane, rec: dict, ctx_names, now: datetime, tz) -> dict | None:
    """One non-draft intent as the company admin may see it. Built field by field from the admin cut of the matrix."""
    seen = _cut(plane, rec)
    if seen is None:
        return None
    people, tb, closure = rec.get("people") or {}, rec.get("time_box") or {}, rec.get("closure") or {}
    chip_key, chip = _chip(rec, now)
    bucket = "overdue" if chip_key == "overdue" else "open" if rec["state"] in OPEN else rec["state"]
    stage = next((s for s in rec.get("stages") or [] if s.get("state") == "open"), None)
    ratings = seen.get("ratings") or {"count": 0, "average": None}
    series = rec["type"] == "pulse"
    closed = rec["state"] == "closed"
    nxt = [n.get("kind") for n in (seen.get("closure") or {}).get("next") or [] if isinstance(n, dict)]
    return {
        "id": rec["id"], "type": rec["type"], "title": seen.get("title") or _fallback_title(rec, tz), "purpose": seen.get("purpose"), "state": rec["state"],
        "bucket": bucket, "stage": ck.STAGE_NAMES.get(stage["key"], str(stage["key"]).replace("_", " ").capitalize()) if stage else None,
        "areas": seen.get("areas") or [], "organiser": ctx_names(people.get("organiser")),
        "sponsor": ctx_names(people.get("sponsor")) or None, "people_more": max(0, seen["people_count"] - 1),
        "opened": _local(tb.get("starts"), tz), "ends": _local(tb.get("ends"), tz), "starts_iso": tb.get("starts") or "",
        "extensions": len([e for e in tb.get("extended_by") or [] if e.get("status") in (None, "approved")]),
        "clock": {"key": chip_key, "text": chip}, "closed_at": closure.get("closed_at") if closed else None,
        "outcome": {"first_line": _first_line((seen.get("closure") or {}).get("what_came_out")), "next": nxt} if closed else None,
        "rating": {"count": 0 if series else ratings["count"], "mean": None if series else ratings["average"], "by_design": series},
        "could_rate": len(people.get("participants") or []),
        "cancelled_by_admin": rec["state"] == "cancelled" and closure.get("cancelled_by_role") == "company_admin",
        "cancel_reason": closure.get("cancel_reason") if rec["state"] == "cancelled" else None,
        "reminded": bool((rec.get("rating") or {}).get("reminded")) if isinstance(rec.get("rating"), dict) else False,
        "_days_over": _days(ck.parse(tb["ends"]), now) if chip_key == "overdue" else 0,
        "_sort": {"title": str(seen.get("title") or "").lower(), "type": rec["type"], "state": rec["state"]},
    }


def _records(plane) -> list[dict]:
    out = []
    for r in S.read_index(plane):
        try:
            rec = S.read_intent(plane, r["id"])
        except S.Unreadable:
            continue
        if rec and rec["state"] != "draft":  # drafts are their creator's alone (ruling 14)
            out.append(rec)
    return out


def _rows(request: Request, plane, now: datetime | None = None) -> list[dict]:
    now, tz, accounts = now or datetime.now(timezone.utc), _tz(plane), request.app.state.account_store
    names = lambda ref: _person(ref, accounts)  # noqa: E731
    area_names = {a["id"]: a["name"] for a in areas_store.listing(profile_store.load(plane))}
    rows = [x for x in (_row(plane, rec, names, now, tz) for rec in _records(plane)) if x]
    for x in rows:  # records hold area ids or, from older writers, names: one name per area so filters and counters do not split
        x["areas"] = sorted({area_names.get(a, a) for a in x["areas"]})
    return rows


def _csv_safe(v) -> str:
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


# ---- filters ----------------------------------------------------------------------------------------------------------------

def _csv(q: dict, key: str) -> set[str]:
    return {x for x in str(q.get(key) or "").split(",") if x}


def _is_unrated(x: dict) -> bool:
    return x["state"] == "closed" and x["type"] != "pulse" and x["rating"]["count"] == 0


def _filter(rows: list[dict], q: dict) -> list[dict]:
    types, states, areas = _csv(q, "type"), _csv(q, "state"), _csv(q, "area")
    org, text = str(q.get("organiser") or "").strip().lower(), str(q.get("q") or "").strip().lower()
    f, t = str(q.get("opened_from") or ""), str(q.get("opened_to") or "")
    out = []
    for x in rows:
        if ((types and x["type"] not in types) or (states and x["state"] not in states) or (org and x["organiser"].lower() != org)
                or (areas and not (set(x["areas"]) & areas or ("none" in areas and not x["areas"])))
                or (f and (not x["opened"] or x["opened"] < f)) or (t and (not x["opened"] or x["opened"] > t))
                or (text and text not in f"{x['title']} {x['purpose']}".lower())
                or (q.get("overdue") == "1" and x["bucket"] != "overdue") or (q.get("at_risk") == "1" and x["clock"]["key"] != "at_risk")
                or (q.get("unrated") == "1" and not _is_unrated(x))):
            continue
        out.append(x)
    return out


def _sort(rows: list[dict], q: dict) -> list[dict]:
    key = q.get("sort") or ""
    if q.get("overdue") == "1":
        return sorted(rows, key=lambda x: -x["_days_over"])
    if q.get("unrated") == "1":
        return sorted(rows, key=lambda x: x["closed_at"] or "", reverse=True)
    pick = {"ends": lambda x: x["ends"], "title": lambda x: x["_sort"]["title"], "type": lambda x: x["_sort"]["type"],
            "state": lambda x: x["_sort"]["state"]}.get(key, lambda x: x["starts_iso"])
    return sorted(rows, key=pick, reverse=(q.get("dir") != "asc") if key in ("", "opened") else q.get("dir") == "desc")


def _public(x: dict) -> dict:
    return {k: v for k, v in x.items() if not k.startswith("_")} | ({"days_overdue": x["_days_over"]} if x["bucket"] == "overdue" else {})


def _counts(rows: list[dict]) -> dict:
    c = {b: sum(1 for x in rows if x["bucket"] == b) for b in ("open", "overdue", "closed", "cancelled")}
    return {**c, "total": len(rows)}


def _north_overdue(rows: list[dict]) -> str | None:
    n = len(rows)
    if not n:
        return None
    cat = load_catalogue()["types"]
    parts = [f"{_plural(n, 'intent is', 'intents are')} past {'its' if n == 1 else 'their'} end."]
    once = sum(1 for x in rows if x["extensions"] == 1)
    more = sum(1 for x in rows if x["extensions"] > 1)
    if once:
        parts.append(f"{once} {'has' if once == 1 else 'have'} been extended once.")
    if more:
        parts.append(f"{more} {'has' if more == 1 else 'have'} been extended more than once.")
    none = sum(1 for x in rows if not x["sponsor"] and "sponsor" in ((cat.get(x["type"]) or {}).get("people") or {}).get("slots", []))
    if none:
        parts.append(f"{none} {'has' if none == 1 else 'have'} no named sponsor.")
    return " ".join(parts)


def _list(request: Request, plane) -> dict:
    q = dict(request.query_params)
    all_rows = _rows(request, plane)
    hit = _sort(_filter(all_rows, q), q)
    try:
        after = max(0, int(q.get("after") or 0))
        limit = min(200, max(1, int(q.get("limit") or PAGE)))
    except ValueError:
        after, limit = 0, PAGE
    page = hit[after:after + limit]
    out = {"items": [_public(x) for x in page], "counts": _counts(hit), "next": after + limit if after + limit < len(hit) else None,
           "tabs": {"overdue": sum(1 for x in all_rows if x["bucket"] == "overdue"), "unrated": sum(1 for x in all_rows if _is_unrated(x))},
           "organisers": sorted({x["organiser"] for x in all_rows if x["organiser"]}), "areas": sorted({a for x in all_rows for a in x["areas"]}),
           "has_no_area": any(not x["areas"] for x in all_rows), "total_all": len(all_rows),
           "closed_in_view": sum(1 for x in hit if x["state"] in ("closed", "cancelled"))}
    if q.get("overdue") == "1":
        out["north"] = _north_overdue(hit)
    if q.get("unrated") == "1":
        out["reminder_note"] = "North reminded the participants once. Nobody else is asked." if any(x["reminded"] for x in hit) else "No reminder was sent."
    return out


@router.get("/api/intents/admin/list")
def get_admin_list(request: Request):
    plane, bad = _guard(request)
    return bad or _list(request, plane)


# ---- counters ---------------------------------------------------------------------------------------------------------------

def _counters(request: Request, plane) -> dict:
    rows = _rows(request, plane)
    doc = profile_store.load(plane)
    names = {a["id"]: a["name"] for a in areas_store.listing(doc)}
    cells: dict[str, dict] = {}

    def add(area: str, x: dict) -> None:
        c = cells.setdefault(area, {}).setdefault(x["type"], {"open": 0, "overdue": 0, "closed": 0, "cancelled": 0})
        c[x["bucket"]] += 1
    for x in rows:
        for a in x["areas"] or ["none"]:
            add(a, x)
    people = doc.get("people") or {}
    tagged_any = any(areas_store.people_areas(p) for p in people.values())
    return {"rows": [{"area": a, "name": names.get(a, "No area" if a == "none" else a), "types": cells[a]}
                     for a in sorted(cells, key=lambda k: (k == "none", names.get(k, k).lower()))],
            "totals": {t: _counts([x for x in rows if x["type"] == t]) for t in load_catalogue()["types"]},
            "untagged": sum(1 for p in people.values() if not areas_store.people_areas(p)) if people and tagged_any else None,
            "areas_set_up": bool(names), "no_area": sum(1 for x in rows if not x["areas"]), "total": len(rows)}


@router.get("/api/intents/admin/counters")
def get_admin_counters(request: Request):
    plane, bad = _guard(request)
    return bad or _counters(request, plane)


# ---- register ---------------------------------------------------------------------------------------------------------------

def _register(request: Request, plane) -> dict:
    q, tz, accounts = dict(request.query_params), _tz(plane), request.app.state.account_store
    rows = [x for x in _filter(_rows(request, plane), q) if x["state"] in ("closed", "cancelled")]
    by_id = {r["id"]: r for r in _records(plane)}
    out = []
    for x in sorted(rows, key=lambda x: x["closed_at"] or "", reverse=True):
        rec = by_id[x["id"]]
        cl, tb = rec.get("closure") or {}, rec.get("time_box") or {}
        closed = x["state"] == "closed"
        in_time = ""
        if closed and tb.get("ends") and cl.get("closed_at"):
            in_time = "yes" if x["clock"]["key"] == "done" else "no"
        mean = x["rating"]["mean"]
        out.append({k: _csv_safe(v) for k, v in {
            "id": x["id"], "type": x["type"], "title": x["title"], "state": x["state"], "areas": ";".join(x["areas"]),
            "organiser": x["organiser"], "sponsor": x["sponsor"] or "", "opened": x["opened"], "time_box_end": x["ends"],
            "closed_at": _local(cl.get("closed_at"), tz, "%Y-%m-%d %H:%M"), "closed_in_time": in_time, "extensions": x["extensions"],
            "summary": cl.get("summary") if closed else "", "what_came_out": cl.get("what_came_out") if closed else "",
            "next": ";".join(n.get("kind", "") for n in cl.get("next") or []) if closed else "",
            "rating_count": "" if x["rating"]["by_design"] else x["rating"]["count"], "rating_mean": "" if mean is None else mean,
            "cancelled_by": "company_admin" if x["cancelled_by_admin"] else "",
            "cancel_reason": x["cancel_reason"] or ""}.items()})
    _log(plane, "register_download", len(out))
    rec_company = request.app.state.entitlements.company(request.state.company_id) or {}
    return {"columns": CSV_COLUMNS, "rows": out, "tz": ck._tz(plane), "company": request.state.company_id,
            "company_name": rec_company.get("name") or request.state.company_id}


@router.get("/api/intents/admin/register")
def get_admin_register(request: Request):
    plane, bad = _guard(request)
    return bad or _register(request, plane)


_VIEWS = {"list": _list, "counters": _counters, "register": _register}


# ---- cancel -----------------------------------------------------------------------------------------------------------------

class Cancel(BaseModel):
    reason: str = ""


def _event(plane, rec: dict, request: Request, at: str) -> None:
    """One events.jsonl line through the one writer; the reason stays in `closure.cancel_reason` (ruling 27), the line holds kinds only."""
    who = {"account": request.state.account_id, "name": _by(request), "role": ADMIN}
    events.point_rec(rec, events.try_append(plane, rec["id"], "cancelled_by_admin", who, None, {}, "act"))


def admin_cancel(request: Request, plane, intent_id: str, reason: str) -> JSONResponse | dict:
    reason = (reason or "").strip()
    if not reason:
        return _fail(400, "Say why you are cancelling this intent.")
    with S.locked(plane):
        try:
            rec = S.read_intent(plane, intent_id)
        except S.Unreadable:
            rec = None
        if rec is None or rec["state"] == "draft":
            return _fail(404, S.NOT_FOUND)
        if rec["state"] not in OPEN:
            return _fail(409, "This intent has just changed. Open it again to see where it stands.")
        at, was = S.now_iso(), rec["state"]
        cl = rec.get("closure") or {}
        cl.update({"closed_by": request.state.account_id, "closed_at": at, "cancel_reason": reason, "cancelled_by_role": "company_admin",
                   "next": [{"kind": "nothing", "ref": None, "reason": reason}]})
        rec.update({"closure": cl, "state": "cancelled"})
        rec.setdefault("history", []).append({"at": at, "by": request.state.account_id, "from": was, "to": "cancelled",
                                               "note": "Cancelled by the company admin"})
        _event(plane, rec, request, at)
        S.write_intent(plane, rec)
    _log(plane, "admin_cancel", 1)
    try:  # link lines at cancel time (spec 20); never undoes the cancel
        from sh_platform.intents import _viewer, links
        links.on_cancel(plane, intent_id, _viewer(request))
    except Exception:  # noqa: BLE001
        pass
    return {"id": intent_id, "state": "cancelled"}


@router.post("/api/intents/{intent_id}/admin-cancel")
def post_admin_cancel(intent_id: str, body: Cancel, request: Request):
    plane, bad = _guard(request)
    return bad or admin_cancel(request, plane, intent_id, body.reason)


# ---- super admin: existence through the kernel ------------------------------------------------------------------------------

def _kernel_plane(request: Request, company_id: str):
    """One company's plane for the super admin, opened on request; None when there is no such company."""
    if vis.SUPER_ADMIN not in (request.state.roles or []):
        return None
    try:
        valid_company_id(company_id)
        if request.app.state.entitlements.company(company_id) is None:
            return None
        return PlaneStore(request.app.state.settings.data_root).plane_for(company_id)
    except (ValueError, LookupError, CrossCompanyError):
        return None


def _existence(plane, now: datetime) -> list[dict]:
    """Title (unless private), type, state, areas, people count, dates, clock words, and the id as a row key. No purpose, organiser, outcome or closure."""
    tz = _tz(plane)
    doc = profile_store.load(plane)
    ctx = vis.Context(titles_private=areas_store.titles_private(doc))
    names = {a["id"]: a["name"] for a in areas_store.listing(doc)}
    out = []
    for rec in _records(plane):
        seen = vis.read_intent(plane, rec, _SUPER_VIEWER, ctx)
        if seen is None:
            continue
        out.append({"id": rec["id"], "title": (seen.get("title") or _fallback_title(rec, tz)) if "title" in seen else None,
                    "title_private": "title" not in seen, "type": rec["type"], "state": rec["state"],
                    "areas": [names.get(a, a) for a in seen.get("areas") or []], "people_count": seen["people_count"],
                    "opened": (seen["time_box"] or {}).get("starts"), "ends": (seen["time_box"] or {}).get("ends"),
                    "clock": _chip(rec, now)[1], "bucket": _chip(rec, now)[0]})
    return sorted(out, key=lambda x: x["opened"] or "", reverse=True)


@router.get("/api/control/companies/{company_id}/intents")
def get_control_companies_by_company_id_intents(company_id: str, request: Request):
    plane = _kernel_plane(request, company_id)
    return {"rows": _existence(plane, datetime.now(timezone.utc))} if plane else _fail(404, "That company does not exist.")


@router.get("/api/control/intents/summary")
def get_control_intents_summary(request: Request):
    """Counts for one company (`?company_id=`, else the first), read through the kernel: type by state, overdue, at risk, last activity."""
    if vis.SUPER_ADMIN not in (request.state.roles or []):
        return _fail(403, SEE_ONLY)
    es = request.app.state.entitlements
    cid = request.query_params.get("company_id") or next((c["company_id"] for c in es.list_companies()), "")
    plane = _kernel_plane(request, cid)
    if plane is None:
        return _fail(404, "That company does not exist.")
    now = datetime.now(timezone.utc)
    recs = _records(plane)
    chips = [_chip(r, now)[0] for r in recs]
    stamps = [t for r in recs for t in (r.get("created_at"), (r.get("closure") or {}).get("closed_at")) if t]
    return {"company_id": cid, "centre_on": es.switches(cid)["centres"].get("intent") is not False,
            "titles_private": areas_store.titles_private(profile_store.load(plane)),
            "by_type": {t: {s: sum(1 for r in recs if r["type"] == t and r["state"] == s) for s in S.STATES[1:]} for t in load_catalogue()["types"]},
            "total": len(recs), "overdue": chips.count("overdue"), "at_risk": chips.count("at_risk"), "last_activity": max(stamps, default=None),
            "centre_use": measures.centre_use(plane, request.query_params.get("window") or "6m")}  # B33 Screen 3: counts per month, no title, person or content
