"""Consume by business view (spec 60, rulings C35 to C37, C41). A lens groups what Consume already shows; it adds no figure.

Code says `lens`; the screen says "business view" (C37). One lens per measure (C35): Lens drafts it, the measure's business owner (or the head of
data) confirms or moves it. Records: `consume/lenses.json` = {"measures": {code: {lens, mark, from, confirmed_by, confirmed_at}}}.
Every count is over measures the viewer may see (feeds `may_see`). Hypotheses (57) and Proving (58) are read from their files as they stand; a
missing or older shape reads as nothing, never as an error.

Routes: GET /api/company/consume/lenses, GET /api/company/consume/lenses/{lens}, POST /api/company/consume/lenses/assign.
`install(app)` mounts these and the card routes (sh_platform/consume/cards.py).
"""
import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from modules.m2_baseline.store import baseline as B
from modules.m2_baseline.store import governed as GS
from sh_platform.consume import feeds
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile import areas as areas_store, store as profile_store, view
from sh_platform.profile.api import _plane, _viewer

log = logging.getLogger(__name__)
router = APIRouter()

LENSES = {
    "new_revenue": ("New revenue", "What is the office earning on what it already holds?"),
    "process_cost": ("Process cost", "What do our routine steps cost in staff hours and fees?"),
    "retention": ("Retention", "Do the family and the next generation keep trusting our reports and service?"),
    "risk": ("Risk", "What could hurt the family's capital: exposures, stale or missing values, concentration?"),
}
NOTE = "A business view groups what is already here. It adds no figure of its own."
NO_FIGURE_LINE = "Not available yet: no measure assigned to this business view"
# words in a measure's name that point at a view; the first view with a hit wins (a draft, never a decision)
WORDS = {"process_cost": ("effort", "hours", "preparation", "reconciled", "needing review", "fees"),
         "new_revenue": ("return", "alpha", "benchmark", "interest", "yield", "performance"),
         "retention": ("definitions", "named owner", "report", "committee"),
         "risk": ("funding", "obligations", "concentration", "exposure", "stale", "conflicts", "exceptions", "evidence", "unfunded", "stress", "headroom", "fx")}
OPEN_STATES = ("noticed", "under_review", "proposed")
VERDICTS = {"working": "Working", "partly": "Partly", "not": "Not working", "not_working": "Not working", "too_early": "Too early"}


def slug(lens: str) -> str:
    return lens.replace("_", "-")


def key_of(slug_: str) -> str | None:
    k = str(slug_).replace("-", "_")
    return k if k in LENSES else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---- the record -----------------------------------------------------------------------------------------------------------------

def _path(plane):
    return plane.path("consume", "lenses.json")


def read_rows(plane) -> dict:
    try:
        doc = read_json_strict(_path(plane), dict)
    except (OSError, ValueError):
        return {}
    rows = (doc or {}).get("measures")
    return {k: v for k, v in rows.items() if isinstance(v, dict) and v.get("lens") in LENSES} if isinstance(rows, dict) else {}


def hypothesis_lenses(plane) -> tuple[dict, dict]:
    """(by measure code: {lens, id}, by intent id: {lens, measure, name}) from intents/hypotheses/*.json, the newest version of each (57)."""
    by_measure, by_intent = {}, {}
    folder = plane.path("intents", "hypotheses")
    for f in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            h = read_json_strict(f, dict)
        except (OSError, ValueError):
            continue
        vs = (h or {}).get("versions")
        v = vs[-1] if isinstance(vs, list) and vs and isinstance(vs[-1], dict) else None
        if not v or v.get("lens") not in LENSES:
            continue
        m = v.get("measure") if isinstance(v.get("measure"), dict) else {}
        code = str(m.get("id") or "").upper()
        if code:
            by_measure.setdefault(code, {"lens": v["lens"], "id": h.get("id")})
        ids = [c.get("intent") for c in h.get("carried_into") or [] if isinstance(c, dict)]
        o = h.get("origin") if isinstance(h.get("origin"), dict) else {}
        ids += [o.get("ref")] if o.get("kind") == "initiative" else []
        for i in filter(None, ids):
            by_intent[str(i)] = {"lens": v["lens"], "measure": code, "name": m.get("name")}
    return by_measure, by_intent


def draft_lens(name: str, code: str, hyp: dict) -> dict | None:
    """Lens's guess for one measure: a hypothesis that names it, else the words of its name. None when nothing points anywhere."""
    if code in hyp:
        return {"lens": hyp[code]["lens"], "mark": "guessed", "from": f"hypothesis {hyp[code]['id']}"}
    low = str(name).lower()
    for lens, words in WORDS.items():
        hit = next((w for w in words if w in low), None)
        if hit:
            return {"lens": lens, "mark": "guessed", "from": f"the measure's name ('{hit}')"}
    return None


def ensure_drafts(plane, measures: list[dict]) -> dict:
    """Rows for every measure; a missing one gets Lens's draft, a confirmed one is never touched. Idempotent (ruling: a draft never overwrites a person)."""
    rows = read_rows(plane)
    hyp, _ = hypothesis_lenses(plane)
    new = {m["code"]: d for m in measures if m["code"] not in rows and (d := draft_lens(m["name"], m["code"], hyp))}
    if new:
        with lock_for(_path(plane)):
            rows = read_rows(plane)
            for c, d in new.items():
                rows.setdefault(c, d)
            write_json_atomic(_path(plane), {"measures": rows})
    return rows


def lens_of(plane, code: str) -> dict:
    """For feeds: {key, name, mark} of a measure's view (read only; None key when none)."""
    r = read_rows(plane).get(code)
    return {"key": r["lens"], "name": LENSES[r["lens"]][0], "mark": r.get("mark")} if r else {"key": None, "name": None, "mark": None}


# ---- who may move a view ---------------------------------------------------------------------------------------------------------

def _business_owner(plane, code: str) -> str | None:
    found = B.baselines(plane)
    base = next((b for b in found if b.get("state") == "signed"), found[0] if found else None)
    if base is None:
        return None
    c = (GS._read(plane, base["id"]).get(code) or {}).get("owners")
    v = c.get("value") if isinstance(c, dict) and c.get("mark") != "unknown" else None
    return v.get("business") if isinstance(v, dict) else None


def may_move(plane, viewer: view.Viewer, code: str) -> bool:
    """The business owner of the measure, or the head of data (as governed.check_confirm allows). Nobody else, the company admin included."""
    owner = _business_owner(plane, code)
    if owner and view.norm(owner) == view.norm(viewer.name) and not viewer.shared_name:
        return True
    try:
        people = profile_store.raw(plane).get("people") or {}
    except (OSError, ValueError, KeyError):
        return False
    def v(p, k):
        c = (p or {}).get(k)
        return c.get("value") if isinstance(c, dict) and c.get("mark") != "unknown" else None
    return any(v(p, "is_head_of_data") is True and ((viewer.account_id and v(p, "account_id") == viewer.account_id) or
                                                    (not viewer.shared_name and view.norm(v(p, "name") or "") == view.norm(viewer.name))) for p in people.values())


def assign(plane, viewer: view.Viewer, code: str, lens: str, measures: list[dict]) -> tuple[int, dict]:
    """(status, body). Confirms the view (same lens) or moves it (another); either way it is stated by the person."""
    if lens not in LENSES or not any(m["code"] == code and m["may_see"] for m in measures):
        return 404, {"detail": "We could not find that."}
    if not may_move(plane, viewer, code):
        return 403, {"detail": "Only the business owner of this measure, or the head of data, can confirm or move its business view."}
    with lock_for(_path(plane)):
        rows = read_rows(plane)
        rows[code] = {"lens": lens, "mark": "stated", "from": "confirmed by a person", "confirmed_by": viewer.name, "confirmed_at": _now()}
        write_json_atomic(_path(plane), {"measures": rows})
    return 200, {"code": code, "lens": lens, "name": LENSES[lens][0], "mark": "stated", "confirmed_by": viewer.name}


# ---- line of work ---------------------------------------------------------------------------------------------------------------

def mine(plane, viewer: view.Viewer, measures: list[dict], by_intent: dict, intents: list[dict]) -> set[str]:
    """Measures where the viewer is a named business, data or process owner; whose governed `affects` names one of their areas; or that an
    intent they take part in aims at. No other signal (spec 60, Rules)."""
    out: set[str] = set()
    me = view.norm(viewer.name)
    found = B.baselines(plane)
    base = next((b for b in found if b.get("state") == "signed"), found[0] if found else None)
    gov = GS._read(plane, base["id"]) if base else {}
    try:
        areas = {view.norm(a) for a in areas_store.areas_of_account(profile_store.load(plane), viewer.account_id)}
    except (OSError, ValueError, KeyError):
        areas = set()

    def val(code, field):
        c = (gov.get(code) or {}).get(field)
        return c.get("value") if isinstance(c, dict) and c.get("mark") != "unknown" else None
    for m in measures:
        o = val(m["code"], "owners")
        if isinstance(o, dict) and me and any(view.norm(n) == me for n in o.values() if isinstance(n, str)):
            out.add(m["code"])
        aff = val(m["code"], "affects")
        if areas and isinstance(aff, list) and areas & {view.norm(a) for a in aff if isinstance(a, str)}:
            out.add(m["code"])
    for r in intents:
        h = by_intent.get(r["id"])
        names = [(r.get("organiser") or {}).get("name")] + [p.get("name") for s in ("sponsor", "owner", "decider") if isinstance((p := (r.get("people") or {}).get(s)), dict)]
        names += [p.get("name") for k in ("participants", "advisers") for p in (r.get("people") or {}).get(k) or [] if isinstance(p, dict)]
        if h and h["measure"] and any(n and view.norm(n) == me for n in names):
            out.add(h["measure"])
    return out


# ---- the building and consider strips -------------------------------------------------------------------------------------------

def _proving(plane, intent_id: str) -> dict | None:
    try:
        p = read_json_strict(plane.path("intents", intent_id, "proving.json"), dict)
    except (OSError, ValueError):
        return None
    return p if isinstance(p, dict) else None


def _verdict(p: dict | None) -> str:
    if not p:
        return "No report yet"
    v = p.get("verdict")
    if not v:
        reps = p.get("reports")
        v = (reps[-1] or {}).get("verdict") if isinstance(reps, list) and reps and isinstance(reps[-1], dict) else None
    v = v.get("value") if isinstance(v, dict) else v
    return VERDICTS.get(str(v), "No report yet")


def building_rows(plane, viewer, rows: list[dict], by_intent: dict, areas) -> list[dict]:
    """Initiatives that are in Build (links.build set) or in Proving, with the viewer's tier deciding the title (05)."""
    from sh_platform.intents import store
    out = []
    for r in rows:
        if r.get("type") != "initiative":
            continue
        rec = store.read_intent(plane, r["id"]) or {}
        proving = _proving(plane, r["id"])
        in_build = bool((rec.get("links") or {}).get("build"))
        if not in_build and proving is None:
            continue
        tier = store.tier_of(r, viewer, areas)
        if tier is None:
            continue
        h = by_intent.get(r["id"]) or {}
        out.append({"id": r["id"], "lens": h.get("lens"), "measure": h.get("measure") or None, "stage": "Proving" if proving is not None else "In Build",
                    "title": r.get("title") if tier != "exists" else "An Initiative you may not open", "href": f"/centre/intent/{r['id']}" if tier != "exists" else None,
                    "organiser": (r.get("organiser") or {}).get("name") or None, "verdict": _verdict(proving) if proving is not None else None})
    return out


def consider_rows(plane, sees, code_to_lens: dict) -> list[dict]:
    """Radar opportunities still open: the hypothesis lens if the record carries one (57), else the view of the first measure it touches."""
    from sh_platform.intents import opportunities
    out = []
    for rec in opportunities.all_records(plane):
        if rec.get("state") not in OPEN_STATES or not sees(rec):
            continue
        hyp = rec.get("hypothesis") if isinstance(rec.get("hypothesis"), dict) else {}
        lens = hyp.get("lens") if hyp.get("lens") in LENSES else next((code_to_lens[m] for m in (rec.get("touches") or {}).get("measures") or [] if m in code_to_lens), None)
        j = rec.get("judgement") if isinstance(rec.get("judgement"), dict) else {}
        out.append({"id": rec["id"], "lens": lens, "title": rec.get("title"), "state": rec["state"], "line": j.get("why") or None,
                    "href": f"/centre/intent/backlog?opportunity={rec['id']}"})
    return out


# ---- the document ---------------------------------------------------------------------------------------------------------------

def compute(plane, viewer, feed: list[dict], briefs: list[dict], rows: list[dict], areas, sees_opp, only_mine: bool = False) -> dict:
    """All four views at once. `feed` is feeds.build()['measures'], `briefs` market briefs, `rows` the intent index rows."""
    assigned = ensure_drafts(plane, feed)
    _, by_intent = hypothesis_lenses(plane)
    seen = [m for m in feed if m["may_see"]]
    line_of_work = mine(plane, viewer, feed, by_intent, rows)
    keep = line_of_work if only_mine else {m["code"] for m in feed}
    to_lens = {c: r["lens"] for c, r in assigned.items()}
    building = building_rows(plane, viewer, rows, by_intent, areas)
    consider = consider_rows(plane, sees_opp, to_lens)
    docs = []
    for lens, (name, question) in LENSES.items():
        codes = [c for c, r in assigned.items() if r["lens"] == lens]
        mine_codes = [c for c in codes if c in keep]
        fm = [m for m in feed if m["code"] in mine_codes]
        visible = [m for m in fm if m["may_see"]]
        bs = [b for b in briefs if {str(c).upper() for c in b.get("measures") or []} & set(mine_codes)]
        bl = [b for b in building if b["lens"] == lens and (not only_mine or b["measure"] in keep)]
        cs = [c for c in consider if c["lens"] == lens]
        docs.append({"key": lens, "slug": slug(lens), "name": name, "question": question, "measures": mine_codes,
                     "counts": {"measures": len(visible), "outside": sum(1 for m in visible if m.get("range_break")), "briefs": len(bs),
                                "building": sum(1 for b in bl if b["stage"] == "In Build"), "proving": sum(1 for b in bl if b["stage"] == "Proving"), "consider": len(cs)},
                     "empty": None if visible else NO_FIGURE_LINE,
                     "_feeds": fm, "_briefs": bs, "_building": bl, "_consider": cs})
    return {"lenses": docs, "not_in_a_lens": sum(1 for m in seen if m["code"] not in assigned), "note": NOTE, "mine": only_mine, "assigned": assigned,
            "has_line_of_work": bool(line_of_work)}


def summary(doc: dict) -> dict:
    return {"lenses": [{k: v for k, v in d.items() if not k.startswith("_")} for d in doc["lenses"]], "not_in_a_lens": doc["not_in_a_lens"],
            "note": doc["note"], "mine": doc["mine"], "has_line_of_work": doc["has_line_of_work"]}


def detail(plane, viewer, doc: dict, key: str) -> dict:
    d = next(x for x in doc["lenses"] if x["key"] == key)
    out = {k: v for k, v in d.items() if not k.startswith("_")}
    feed = []
    for m in sorted(d["_feeds"], key=lambda m: (not m.get("range_break"), m["code"])):  # range breaks first
        feed.append(m if m["may_see"] else {**m, "restricted": f"Restricted: ask {m.get('owner') or 'the owner'}"})
    out["feeds"] = feed
    out["outside_line"] = None if not out["counts"]["measures"] else (f"{out['counts']['outside']} of {out['counts']['measures']} outside their usual range"
                                                                      if out["counts"]["outside"] else "All inside the usual range")
    out["briefs"] = [{"id": b.get("id"), "title": b.get("title"), "summary": b.get("summary"), "date": b.get("date"), "source": b.get("source"), "outside": True,
                      "measure_moves": b.get("measure_moves") or []} for b in d["_briefs"]]
    out["building"], out["consider"] = d["_building"], d["_consider"]
    out["measure_rows"] = [{"code": m["code"], "name": m["name"], "mark": doc["assigned"][m["code"]].get("mark"), "confirmed_by": doc["assigned"][m["code"]].get("confirmed_by"),
                            "can_move": may_move(plane, viewer, m["code"])} for m in d["_feeds"]]
    out["others"] = [{"key": k, "name": LENSES[k][0]} for k in LENSES if k != key]
    out["try_what_if"] = f"/centre/consume/what-if?lens={d['slug']}"
    return out


# ---- routes ---------------------------------------------------------------------------------------------------------------------

def _briefs(request: Request) -> list[dict]:
    try:
        from sh_platform.consume import market
        doc = market.get_api_company_market(request)
        return doc.get("briefs") or [] if isinstance(doc, dict) else []
    except Exception as e:  # noqa: BLE001  outside material failing must never hide the lenses
        log.warning("business views: market briefs unavailable: %s", type(e).__name__)
        return []


def _world(request: Request, only_mine: bool) -> tuple:
    from sh_platform.intents import opportunities, store
    plane, viewer = _plane(request), _viewer(request)
    feed = feeds.build(plane, viewer, feeds._pack_names(request))["measures"]
    ctx = opportunities.Ctx(request, plane)
    rows = store.read_index(plane)
    doc = compute(plane, viewer, feed, _briefs(request), rows, store.areas_of(plane, viewer), ctx.sees, only_mine)
    return plane, viewer, doc, feed


def _flag(request: Request) -> bool:
    return request.query_params.get("mine") in ("1", "true")


@router.get("/api/company/consume/lenses")
def get_lenses(request: Request):
    return summary(_world(request, _flag(request))[2])


@router.get("/api/company/consume/lenses/{lens}")
def get_lens(request: Request, lens: str):
    key = key_of(lens)
    if key is None or not re.fullmatch(r"[a-z-]{1,20}", lens):
        return JSONResponse({"detail": "We could not find that."}, status_code=404)
    plane, viewer, doc, _ = _world(request, _flag(request))
    return detail(plane, viewer, doc, key)


@router.post("/api/company/consume/lenses/assign")
async def post_assign(request: Request):
    try:
        body = await request.json()
    except ValueError:
        body = None
    code, lens = (body or {}).get("measure"), key_of(str((body or {}).get("lens") or ""))
    if not (isinstance(body, dict) and isinstance(code, str) and lens):
        return JSONResponse({"detail": "Send the measure code and the business view."}, status_code=422)
    plane, viewer = _plane(request), _viewer(request)
    status, out = assign(plane, viewer, code.upper(), lens, feeds.build(plane, viewer, feeds._pack_names(request))["measures"])
    return JSONResponse(out, status_code=status)


def install(app) -> None:
    """Called once from sh_platform/app.py: the lens routes and the context card routes."""
    from sh_platform.consume import cards
    app.include_router(router)
    app.include_router(cards.router)
