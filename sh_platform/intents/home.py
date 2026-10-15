"""The Intent Centre home (spec 04) with first run and empty states (spec 18): GET /api/intents/home.

One call gives the page everything: lanes of intent cards per viewer area plus Company-wide, the Your turn lines, past intents, the four
counters (file 19: M01, M02, M13, M08) with the ids each was computed from, and the first-run payload. Nothing is written.

Records come through B01's store (`store.read_intent`); who sees what is B03's matrix (`visibility.rows_for`), never decided here.
The four counters are B33's `measures.home_counters` (file 19 is their single source); this file only words them.
"""
import logging
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.intents import _plane, _viewer, measures, store, visibility
from sh_platform.intents import pack as pack_mod
from sh_platform.intents import clock
from sh_platform.intents.lifecycle import company_zone
from sh_platform.profile import areas as areas_store, store as profile_store

log = logging.getLogger(__name__)
router = APIRouter()

TYPES_FILE = Path(__file__).resolve().parents[2] / "modules" / "m1_intent" / "contracts" / "intent_types.yaml"
TYPE_ORDER = ("initiative", "brainstorm", "pulse", "problem", "decision")
TYPE_NAMES = {"initiative": "Initiative", "brainstorm": "Brainstorm", "pulse": "Weekly check-in", "problem": "Problem", "decision": "Decision"}
TYPE_LINES = {  # spec 18, "The five type lines"
    "initiative": "Run a project or a new initiative, with a clear goal and the people behind it.",
    "brainstorm": "Think with four to eight people about an idea or a problem.",
    "pulse": "Every week, an operations area says what ran, what broke and what is on its mind.",
    "problem": "Something is wrong in operations and needs an owner and a fix.",
    "decision": "One decision to make and record, with the options considered.",
}
ROLE_ORDER = ("organiser", "sponsor", "decider", "owner", "reporter", "participant", "adviser", "affected", "observer")
SLOTS = {"organiser": "organiser", "sponsor": "sponsor", "decider": "decider", "owner": "owner", "reporter": "reporter",
         "participants": "participant", "advisers": "adviser", "affected": "affected", "observers": "observer"}
COUNTED = ("organiser", "sponsor", "decider", "owner", "reporter", "participants", "affected")  # observers excluded (04, People count)
CONFIRMER = {"initiative": "sponsor", "decision": "decider", "problem": "owner"}  # ruling 25
RUNNING = ("open", "in_session", "closing")
COMPANY_WIDE = "company-wide"
NAMED = "named"  # cards in areas the viewer is not in but may see: the viewer is named on them, or is the company admin
DRAFTS = "drafts"  # the starter's drafts that name no area yet: not Company-wide, which would tell the viewer it is for everyone
NA = "Not available yet"


def _records(plane) -> list[dict]:
    """Every intent record through the store. A damaged record is skipped and logged, never shown half."""
    out = []
    for i in store._ids_on_disk(plane):
        try:
            rec = store.read_intent(plane, i)
        except store.Unreadable:
            log.warning("an intent record could not be read: %s", i)
            continue
        if rec:
            out.append(rec)
    return out


@lru_cache(maxsize=1)
def _types() -> dict:
    return (yaml.safe_load(TYPES_FILE.read_text(encoding="utf-8")) or {}).get("types", {})


def _v(cell: Any) -> Any:
    return cell.get("value") if isinstance(cell, dict) and "mark" in cell else cell


def _list(value: Any) -> list:
    return [v for v in (value if isinstance(value, list) else [value]) if v]


def _key(person: Any) -> str:
    return str(person.get("account_id") or person.get("name") or "") if isinstance(person, dict) else str(person)


def _roles(rec: dict, ctx: dict) -> list[str]:
    people = rec.get("people") or {}
    got = {SLOTS[k] for k in SLOTS if any(visibility._is(x, ctx["viewer"]) for x in _list(people.get(k)))}
    if rec.get("state") == "draft" and rec.get("created_by") == ctx["viewer"].account_id:
        got.add("organiser")
    return [r for r in ROLE_ORDER if r in got]


def _visible(rec: dict, ctx: dict) -> bool:
    """B03's matrix decides (a draft reaches its starter only, ruling 14). Records name areas by name or id and B03 compares ids, so the
    areas are mapped to ids first; the reserved "company-wide" token makes a running intent's existence visible to everyone (04, Fields).
    ponytail: local workaround until `visibility.rows_for` does both itself (see the T05 report)."""
    to_id = ctx.get("area_id", lambda a: a)
    areas = [to_id(a) for a in rec.get("areas") or []]
    if visibility.rows_for({**rec, "areas": areas}, ctx["viewer"], ctx["vctx"]):
        return True
    return COMPANY_WIDE in areas and rec.get("state") != "draft"


def _when(text: Any, tz) -> datetime | None:
    if not text:
        return None
    try:
        d = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(tz)


def _days(rec: dict, now: datetime, tz) -> tuple[str, int | None, bool]:
    """The card's time line, read from the stage clock's rule (clock.py): "3 days left", "6 hours left", "Overdue by 1 working day"."""
    if rec.get("state") == "draft":
        return "Time box starts when opened", None, False
    if rec.get("state") in clock.CLOSED:
        return str(rec["state"]).capitalize(), None, False
    tb = rec.get("time_box") or {}
    ends = _when(tb.get("ends"), tz)
    if ends is None:
        return f"{NA} (no end date is set)", None, False
    c = clock.clock(clock.parse(tb.get("starts") or tb["ends"]), clock.parse(tb["ends"]), now)
    over = c["state"] == "overdue"
    n = -(-c["hours_left"] // 24) if over else c["working_days_left"]
    if rec.get("type") == "pulse":
        return (f"Ended {ends:%A}" if over else f"Ends {ends:%A}"), n, False
    return c["words"], n, over or c["unit"] == "hours"


def _stage(rec: dict) -> tuple[str, str]:
    stages = [s for s in rec.get("stages") or [] if isinstance(s, dict)]
    open_ = next((s for s in stages if s.get("state") == "open"), None)
    if not open_ and rec.get("state") != "draft":  # closing with every stage closed: the last one reached
        open_ = next((s for s in reversed(stages) if s.get("closed_at")), None)
    if not open_:
        return "", "Not started"
    names = {s["key"]: s["name"] for s in _types().get(rec.get("type"), {}).get("stages", [])}
    return open_.get("key", ""), names.get(open_.get("key"), str(open_.get("key", "")).replace("_", " ").capitalize())


def _people_count(rec: dict) -> int:
    people = rec.get("people") or {}
    return len({_key(x) for k in COUNTED for x in _list(people.get(k))})


def _proving_fields(plane, iid) -> dict:
    """Spec 58 chip fields (C20) for a card; nothing when the intent has no Proving."""
    try:
        from sh_platform.intents import proving  # lazy: proving imports store
        return proving.index_fields(proving.read_proving(plane, iid))
    except Exception:  # noqa: BLE001 - a card never fails on Proving
        return {}


def _card(rec: dict, ctx: dict) -> dict:
    roles = _roles(rec, ctx)
    days, n, warn = _days(rec, ctx["now"], ctx["tz"])
    key, stage = _stage(rec)
    org = (rec.get("people") or {}).get("organiser")
    ext = (rec.get("time_box") or {}).get("extended_by") or []
    count = _people_count(rec)
    return {
        "id": rec.get("id"), "type": rec.get("type"), "type_name": TYPE_NAMES.get(rec.get("type"), str(rec.get("type"))),
        "title": (rec.get("title") or "").strip() or "Untitled intent", "state": rec.get("state"), "stage_key": key, "stage": stage,
        "days": days, "days_n": n, "days_warn": warn, "organiser": ctx["names"](org) if org else "No organiser",
        "people": "0 invited yet" if count == 0 and rec.get("state") == "draft" else f"{count} {'person' if count == 1 else 'people'}",
        "your_role": roles[0].capitalize() if roles else None, "mine": bool(roles) or rec.get("state") == "draft",
        "extended": bool(ext), "extended_note": "; ".join(f"{ctx['names'](e.get('by'))}: {e.get('reason', '')}" for e in ext if isinstance(e, dict)),
        "affects_you": roles == ["affected"] or (not roles and not ctx["admin"] and rec.get("state") != "draft"),  # affected and no stronger role (spec 47)
        "areas": list(rec.get("areas") or []), "href": f"/centre/intent/{rec.get('id')}",
    }


def _lanes(cards: list[dict], ctx: dict) -> list[dict]:
    """One lane per area the viewer belongs to (named by the profile), then Company-wide, then "Named on" for cards in areas the viewer is
    not in, then "Your drafts" once (a draft is only ever in that lane). A card appears in each of its areas the viewer belongs to; the
    second and later carry "Also in" (04, Rules)."""
    order = list(ctx["areas"])
    mine = set(order) | {COMPANY_WIDE}
    named = {c["id"] for c in cards if c.get("mine")}
    placed: dict[str, list[dict]] = {}
    for c in cards:
        if c["state"] == "draft":
            homes = [DRAFTS]
        else:
            homes = [a for a in c["areas"] if a in mine] or ([NAMED] if c["areas"] else [COMPANY_WIDE])
        for i, a in enumerate(homes):
            placed.setdefault(a, []).append({"id": c["id"], "also_in": ctx["area_name"](homes[0]) if i else None})
    # "more": the lane's cards the viewer is not named on, which the default "Mine" view leaves out (W2F1: the count never promises what the list does not show)
    lanes = [{"id": a, "name": ctx["area_name"](a), "cards": placed.get(a, []), "more": sum(x["id"] not in named for x in placed.get(a, []))} for a in order + [COMPANY_WIDE]]
    if NAMED in placed:
        lanes.append({"id": NAMED, "name": "Other areas" if ctx["admin"] else "Named on", "cards": placed[NAMED], "more": sum(x["id"] not in named for x in placed[NAMED])})
    if DRAFTS in placed:
        lanes.append({"id": DRAFTS, "name": "Your drafts", "cards": placed[DRAFTS], "more": 0})
    return lanes


def _month(d: datetime | None, now: datetime) -> bool:
    return d is not None and (d.year, d.month) == (now.year, now.month)


def _missing(m: dict, fallback: str) -> str:
    """B33's `missing` ("Not available yet. No ratings have been given.") as the tile's second line (spec 18, the rule)."""
    why = str(m.get("missing") or "").removeprefix("Not available yet.").strip().rstrip(".") or fallback
    return f"Missing: {why[0].lower()}{why[1:]}"


def counters(hc: dict | None, admin: bool) -> list[dict]:
    """The four home tiles from B33's `measures.home_counters` (file 19 is the single source). A tile shows a number only when a record it
    traces to exists; otherwise "Not available yet" and what is missing. `hc` None: the measures did not load."""
    scope = "All intents" if admin else "Intents you can see"
    spec = (("M01", "Intents opened this month", "This month"), ("M02", "Closed inside the time box", "This month"),
            ("M13", "Average rating", "Last six months"), ("M08", "Build-ready charters", "This quarter"))
    out = []
    for key, label, period in spec:
        m = (hc or {}).get(key) or {"missing": "The measures did not load"}
        value, note = None, f"{period}. {scope}"
        if m.get("missing") is None:
            if key == "M01":
                value = str(m.get("value"))
            elif key == "M02" and m.get("denominator"):
                value = f"{m['numerator']} of {m['denominator']}"
            elif key == "M13" and m.get("ratings"):  # per type (spec 19): a type with fewer than three ratings is not averaged
                n, per = m["ratings"], (m.get("by_type") or {}).items()
                rows = [t for t, v in per if v.get("mean") is not None]
                value = "; ".join(f"{TYPE_NAMES.get(t, t)} {v['mean']} from {v['ratings']} ratings" for t, v in per if t in rows) or "Fewer than three ratings"
                note = note if rows else f"{n} rating{'s' if n != 1 else ''}. {period}. {scope}"
            elif key == "M08":
                value = f"{m.get('waiting', 0)} waiting, {m.get('handed', 0)} handed over"
        missing = None if value is not None else _missing(m, {"M02": "Nothing has closed this month", "M13": "No ratings in the last six months"}.get(key, "No record yet"))
        out.append({"key": key, "label": label, "value": value or NA, "note": missing or note, "ids": list(m.get("ids") or [])})
    return out


def _your_turn(recs: list[dict], ctx: dict) -> list[dict]:
    """Nira's lines (suggestions): closing intents wait on the organiser and the type's confirmer; running stages wait on the people who
    add to them. Ordered by days left, then by type order (04, Agent behaviour)."""
    lines = []
    for r in recs:
        if r.get("state") not in RUNNING:
            continue
        roles = set(_roles(r, ctx))
        asked = any(e.get("person_id") == ctx["viewer"].account_id and e.get("status") == "invited" and e.get("role") != "affected" for e in r.get("people_detail") or [])
        if asked:  # W2F1: an unanswered invitation is the first thing that waits
            what = "Accept or decline the invitation"
        elif r.get("type") == "pulse":  # a check-in week is answered or closed on its own screen; Nira's list (/waiting) says which
            continue
        elif r["state"] == "closing":
            if "organiser" in roles:
                what = "Confirm the closure"
            elif CONFIRMER.get(r.get("type")) in roles:
                what = "Sign off the closure"
            else:
                continue
        elif roles & {"participant", "owner", "decider", "reporter"}:
            what = f"{_stage(r)[1]} is open for you"
        else:
            continue
        days, n, warn = _days(r, ctx["now"], ctx["tz"])
        lines.append({"id": r.get("id"), "what": what, "title": (r.get("title") or "").strip() or "Untitled intent", "days": days,
                      "days_warn": warn, "href": f"/centre/intent/{r.get('id')}", "_n": n if n is not None else 10**6,
                      "_t": TYPE_ORDER.index(r["type"]) if r.get("type") in TYPE_ORDER else 9})
    lines.sort(key=lambda x: (x["_n"], x["_t"]))
    return [{k: v for k, v in x.items() if not k.startswith("_")} for x in lines]


def _past(recs: list[dict], ctx: dict) -> list[dict]:
    rows = []
    for r in recs:
        if r.get("state") not in ("closed", "cancelled"):
            continue
        c = r.get("closure") or {}
        at = _when(c.get("closed_at"), ctx["tz"])
        if at and at > ctx["now"]:  # a closed date is never after today
            at = ctx["now"]
        if r["state"] == "cancelled":
            line = f"Cancelled: {c.get('cancel_reason')}" if c.get("cancel_reason") else "Cancelled"
        else:
            line = (c.get("one_liner") or "").strip()[:140] or "Closed without a summary"
        href = f"/centre/intent/{r.get('id')}/charter" if r.get("type") == "initiative" and r["state"] == "closed" else f"/centre/intent/{r.get('id')}"
        rows.append({"id": r.get("id"), "type": r.get("type"), "type_name": TYPE_NAMES.get(r.get("type"), ""), "state": r["state"],
                     "title": (r.get("title") or "").strip() or "Untitled intent", "date": at.date().isoformat() if at else None,
                     "one_liner": line, "href": href, "_at": at.isoformat() if at else ""})
    rows.sort(key=lambda x: x["_at"], reverse=True)
    return [{k: v for k, v in x.items() if k != "_at"} for x in rows]


def _suggestions(pack) -> dict:
    """Spec 18: the pack's first intents through B32's `pack.first_intents`; EmptyPack gets the honest line, never another industry's."""
    if getattr(pack, "empty", True):
        return {"state": "no_pack", "line": "No industry knowledge is available yet for this industry. You can still start from the five kinds below."}
    label = str(pack.label)
    items = [{"id": i["suggestion_id"], "type": i["type"], "type_name": TYPE_NAMES[i["type"]], "title": i["title"], "purpose": i["purpose"]}
             for i in pack_mod.first_intents(pack)["items"]][:3]  # the cap of three is file 49's
    if not items:
        return {"state": "not_yet", "line": f"{NA}. The {label.lower()} pack has no first intents yet."}
    return {"state": "ok", "heading": f"Suggested first, for a {label.lower()}", "strip": "Suggested from what others in the industry usually do",
            "source": f"Pack: {label}, version {pack.version}", "items": items}


def _type_rows() -> list[dict]:
    t = _types()
    def chip(k: str) -> str:
        if k == "pulse":
            return "One week, repeats"
        d = t.get(k, {}).get("time_box_days")
        return f"{d} working days" if d else NA
    return [{"type": k, "name": TYPE_NAMES[k], "line": TYPE_LINES[k], "chip": chip(k)} for k in TYPE_ORDER]


def _earlier(plane) -> dict | None:
    try:
        walls = sorted(f.stem for f in plane.path("intents", "m1_intent", "sessions").glob("*.json"))
        charters = sorted(f.stem for f in plane.path("intents", "m1_intent", "charters").glob("*.json"))
    except OSError:
        return {"line": f"Earlier work: {NA} (the sessions list did not load)", "walls": [], "charters": []}
    if not walls and not charters:
        return None
    def n(k: int, word: str) -> str:
        return f"{k} {word}" + ("" if k == 1 else "s")
    return {"line": f"Earlier work: {n(len(walls), 'wall')} and {n(len(charters), 'charter')}",
            "walls": [{"label": f"Wall {i + 1}", "href": f"/centre/intent/wall/{w}"} for i, w in enumerate(walls)],
            "charters": [{"label": f"Charter {i + 1}", "href": f"/centre/intent/charter/{c}"} for i, c in enumerate(charters)]}


def build_home(recs: list[dict], ctx: dict) -> dict:
    """The page from the records and the viewer context. Pure, so tests feed it records directly."""
    seen = [r for r in recs if _visible(r, ctx)]
    lane_recs = [r for r in seen if r.get("state") in RUNNING or r.get("state") == "draft"]
    to_id = ctx.get("area_id", lambda a: a)
    cards = [{**c, "areas": list(dict.fromkeys(to_id(a) for a in c["areas"])), **(_proving_fields(ctx["plane"], c["id"]) if ctx.get("plane") is not None else {})} for c in (_card(r, ctx) for r in lane_recs)]
    now = ctx["now"]
    running = sum(r.get("state") in RUNNING for r in seen)
    closed_month = sum(_month(_when((r.get("closure") or {}).get("closed_at"), ctx["tz"]), now) for r in seen if r.get("state") == "closed")
    if not ctx["admin"] and not ctx["areas"]:
        screen = "no_areas"
    else:
        screen = "home" if seen else "first_run"
    past = _past(seen, ctx)
    mine_running = sum(c["mine"] for c in cards if c["state"] in RUNNING)
    yours = f", {mine_running} of them yours" if not ctx["admin"] and running and mine_running != running else ""
    return {
        "screen": screen,
        "subline": f"{running} {'intent' if running == 1 else 'intents'} running in your areas{yours}, {closed_month} closed this month" if seen else "No intents yet",
        "cards": cards, "lanes": _lanes(cards, ctx), "your_turn": _your_turn(seen, ctx),
        "past": past[:10], "past_total": len(past),
        "counters": counters(ctx.get("measures"), ctx["admin"]) if seen else [],
    }


@router.get("/api/intents/home")
def get_intents_home(request: Request):
    try:
        plane = _plane(request)
    except PermissionError:
        return JSONResponse({"detail": "Your company space could not be opened. Please ask your administrator."}, status_code=403)
    st, viewer = request.app.state, _viewer(request)
    acct, admin = viewer.account_id, "company_admin" in viewer.roles
    profile = profile_store.load(plane)
    me = next((p for p in (profile.get("people") or {}).values() if isinstance(p, dict) and _v(p.get("account_id")) == acct), {})
    listing = [a for a in areas_store.listing(profile) if a["status"] == "active"]
    names = {a["id"]: str(a["name"] or a["id"]) for a in areas_store.listing(profile)}
    by_name = {str(a["name"]).strip().lower(): a["id"] for a in areas_store.listing(profile) if a["name"]}
    vctx = visibility.context_for(plane, viewer)
    areas = [a["id"] for a in listing] if admin else [a["id"] for a in listing if a["id"] in vctx.areas]
    tz = company_zone(plane)
    now = datetime.now(tz)
    try:
        hc = measures.home_counters(plane, viewer)
    except Exception:  # noqa: BLE001  a failure in the measures must not take the home down; the tiles say they did not load
        log.exception("the home counters could not be worked out")
        hc = None
    accounts = {a["account_id"]: a for a in st.account_store.in_company(request.state.company_id)}

    def person(p: Any) -> str:
        if isinstance(p, dict):
            return str(p.get("name") or (accounts.get(str(p.get("account_id"))) or {}).get("display_name") or "")
        return str((accounts.get(str(p)) or {}).get("display_name") or p or "")

    def area_id(a: Any) -> str:
        low = str(a).strip().lower()
        return COMPANY_WIDE if low == COMPANY_WIDE else by_name.get(low) or (low if low in names else str(a))

    ctx = {"plane": plane, "viewer": viewer, "vctx": vctx, "admin": admin, "measures": hc, "areas": areas, "now": now, "today": now.date(), "tz": tz, "names": person,
           "area_id": area_id,  # a record that names an area by its name, in any case, joins that area's lane
           "area_name": lambda a: "Company-wide" if a == COMPANY_WIDE else names.get(a, a)}
    out = build_home(_records(plane), ctx)
    rec = st.entitlements.company(request.state.company_id) or {}
    company = rec.get("name") or "your company"
    admin_name = next((a["display_name"] for a in accounts.values() if "company_admin" in a["roles"] and not a.get("disabled")), None)
    account = st.account_store.get(acct) or {}
    out["viewer"] = {"name": viewer.name, "first_name": viewer.name.split(" ")[0] if viewer.name else "", "email": account.get("email", ""),
                     "admin": admin, "may_start": admin or _v(me.get("is_organiser")) is True,
                     "opportunities": bool({"owner", "company_admin", "sponsor", "analyst"} & set(viewer.roles)),  # GET /api/intents/opportunities answers these
                     "governed": bool({"company_admin", "sponsor"} & set(viewer.roles)),  # the Governed state card and its /api/profile read
                     "areas": [{"id": a, "name": ctx["area_name"](a)} for a in areas]}
    out["first_run"] = {
        "opening": f"Welcome. Nothing has been started at {company} yet. Tell me what you intend to do and I will ask the right questions and keep the clock.",
        "suggestions": _suggestions(st.packs.load(rec["industry"])) if rec.get("industry") else _suggestions(None),
        "types": _type_rows(),
        "earlier": _earlier(plane) if admin or out["viewer"]["may_start"] else None,
        "admin_name": admin_name,
    }
    return out
