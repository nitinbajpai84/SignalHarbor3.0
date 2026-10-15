"""B37: the source map of an intent, in Define (`?tab=source-map`). Each data source the baseline names is placed on impact (how many Must and
Should measures it feeds) against readiness (arrival, owner confirmed, fields known, data class set); Lens drafts "strategic" or "not strategic"
from that position and the analyst or organiser confirms it with a reason. Positions are computed at read time from the catalogue; the
result is written to `intents/<id>/source_map.json` (provenance cells) for Build room 0 and the knowledge map (`read_map`).

The zones are module 3's (D-036: the line sits at zero on each axis), so a source that is high and ready reads "p1", and so on.
"""
import re
from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from sh_platform.intents import _plane, _viewer
from sh_platform.intents import store as S
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CrossCompanyError
from sh_platform.profile import view as pview

router = APIRouter()

FULL = 4                      # four measures, or four of the four checks, fill an axis; the line is at zero, so 2 is where "high" and "ready" begin
PRIORITIES = ("must", "should")
CHECKS = (("arrival", "Arrival known"), ("owner", "Owner confirmed"), ("fields", "Fields known"), ("class", "Data class set"))
ZONES = {"p1": "Ready to scan, priority 1", "p2": "Ready to scan, priority 2", "identify": "To be identified", "unknown": "Not placed yet: sort this out first"}
RESTRICTED = "A restricted source"
REASON_MIN, REASON_MAX = 5, 300
UNREADABLE = "The source map could not be read. Please tell your administrator."


def zone(impact: float, readiness: float) -> str:
    return ("p1" if readiness >= 0 else "unknown") if impact >= 0 else ("p2" if readiness >= 0 else "identify")


def _score(k: int) -> float:
    return round(2 * min(k, FULL) / FULL - 1, 2)


def _t(cell) -> str:
    v = cell.get("value") if isinstance(cell, dict) and "mark" in cell else cell
    if isinstance(cell, dict) and cell.get("mark") == "unknown":
        return ""
    return "; ".join(map(str, v)) if isinstance(v, (list, tuple)) else ("" if v is None else str(v).strip())


def _ids(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"[,;]", text) if p.strip()]


def _read(plane, *parts):
    try:
        return read_json_strict(plane.path(*parts))
    except (OSError, ValueError, CrossCompanyError):
        return None


def _cell(value, mark: str, by: str, src: str, at: str, **more) -> dict:
    return {"value": value, "mark": mark, "by": by, "from": src, "at": at, **more}


def file_of(plane, intent_id: str):
    return plane.path("intents", intent_id, "source_map.json")


def read_map(plane, intent_id: str) -> dict | None:
    """The written map, for the cards that read it (Build room 0, the knowledge map). None when nobody has drafted it yet."""
    d = _read(plane, "intents", intent_id, "source_map.json")
    return d if isinstance(d, dict) and isinstance(d.get("sources"), dict) else None


# ---- measures and their priority ------------------------------------------------------------------------------------------------

def _measure_guard_ok(gov: dict, viewer) -> bool:
    """Module 3's rule: personal data not ruled out, or sensitive, makes a measure restricted; the named pass, else the company admin."""
    gov = gov if isinstance(gov, dict) else {}
    if gov.get("personal", "not_sure") == "no" and not gov.get("sensitive"):
        return True
    if viewer is None:
        return True
    names = {pview.norm(n) for n in gov.get("may_see") or [] if str(n).strip()}
    return "company_admin" in viewer.roles if not names else pview.norm(viewer.name) in names and not viewer.shared_name


def _measures(plane, bid: str, charter_id, viewer) -> dict[str, dict]:
    cat = _read(plane, "intents", "m2_baseline", bid, "catalogue.json") or {}
    gov = {str(k.get("id")): k for k in _read(plane, "intents", "m2_baseline", bid, "kpis.json") or [] if isinstance(k, dict)}
    charter = _read(plane, "intents", "m1_intent", "outcomes", f"{charter_id}.json") if charter_id else None
    prio = {str(p.get("id")): str(p.get("priority") or "").lower() for p in (charter or {}).get("problems") or [] if isinstance(p, dict)}
    out = {}
    for r in cat.get("kpis") or []:
        mid = _t(r.get("KPI ID"))
        g = gov.get(mid, {})
        p = next((prio[x] for x in map(str, g.get("problem_ids") or []) if prio.get(x)), "") or _t(r.get("Priority")).lower()
        ok = _measure_guard_ok(g.get("governance"), viewer)
        out[mid] = {"id": mid, "name": _t(r.get("KPI name")) if ok else "A restricted measure", "priority": p, "restricted": not ok}
    return out


# ---- the positions --------------------------------------------------------------------------------------------------------------

def _fed(cat: dict, sid: str) -> list[str]:
    tabs = [t for t in cat.get("tables") or [] if _t(t.get("Source ID")) == sid]
    tids = {_t(t.get("Item ID")) for t in tabs}
    found = [k for t in tabs for k in _ids(_t(t.get("Related KPIs")))]
    found += [k for f in cat.get("fields") or [] if _t(f.get("Item ID")) in tids for k in _ids(_t(f.get("Feeds KPI")))]
    return list(dict.fromkeys(found))


def _field_count(cat: dict, sid: str) -> int:
    tids = {_t(t.get("Item ID")) for t in cat.get("tables") or [] if _t(t.get("Source ID")) == sid}
    return sum(1 for f in cat.get("fields") or [] if _t(f.get("Item ID")) in tids)


def _item(row: dict) -> dict:
    """The guard's input: module 2's source rule reads `personal_data` and `may_see` as cells."""
    names = [n.strip() for n in re.split(r"[,;]", _t(row.get("Who may see it"))) if n.strip()]
    return {"personal_data": {"value": _t(row.get("Contains personal data?")), "mark": "stated"}, "may_see": {"value": names, "mark": "stated"}}


def positions(plane, intent: dict, viewer=None) -> dict:
    """{available, missing?, sources: [...], left_out: n}. `viewer` None sees every source (the file's writer); a source the viewer may not see
    comes back as a silhouette with no name, owner or number. Every figure carries the records it was counted from."""
    refs = intent.get("refs") or {}
    bid = next(iter(refs.get("baseline_ids") or []), None)
    cat = _read(plane, "intents", "m2_baseline", bid, "catalogue.json") if bid else None
    if not isinstance(cat, dict):
        return {"available": False, "missing": "No baseline catalogue has been created for this intent yet.", "baseline_id": bid, "sources": []}
    extras = (_read(plane, "intents", "m2_baseline", bid, "data_sources.json") or {}).get("sources") or {}
    measures = _measures(plane, bid, refs.get("charter_outcome_id"), viewer)
    shut = pview.Viewer("", frozenset())
    out, left, hidden = [], 0, 0
    for row in cat.get("sources") or []:
        sid = _t(row.get("Source ID"))
        ex = extras.get(sid) if isinstance(extras.get(sid), dict) else {}
        if ex.get("left_out"):
            left += 1
            continue
        item = _item(row)
        closed = not pview.sees_source(item, shut)
        if viewer is not None and closed and not pview.sees_source(item, viewer):
            hidden += 1
            out.append({"id": f"restricted-{hidden}", "name": RESTRICTED, "restricted": True, "silhouette": True})
            continue
        name = _t(row.get("Source name")) or sid
        fed = [measures[k] for k in _fed(cat, sid) if measures.get(k, {}).get("priority") in PRIORITIES]
        n_fields = _field_count(cat, sid)
        said = _t(row.get("Contains personal data?")).lower()
        arrival = (_t(row.get("How often it arrives")), _t(row.get("Where it lands or lives")))
        confirmed = _t(row.get("Confirmed by")) or _t(ex.get("confirmed_by"))
        checks = [
            {"key": "arrival", "ok": all(arrival), "trace": f"catalogue, {name}: how often it arrives and where it lands"},
            {"key": "owner", "ok": bool(confirmed), "trace": f"catalogue, {name}: confirmed by " + (confirmed or "no one yet")},
            {"key": "fields", "ok": n_fields > 0, "trace": f"catalogue fields: {n_fields} listed for {name}"},
            {"key": "class", "ok": said.startswith(("yes", "no")), "trace": f"catalogue, {name}: personal data answer is " + (said or "not given")},
        ]
        k = sum(c["ok"] for c in checks)
        imp, rdy = _score(len(fed)), _score(k)
        z = zone(imp, rdy)
        out.append({"id": sid, "name": name, "restricted": closed, "silhouette": False,
                    "impact": {"count": len(fed), "must": sum(m["priority"] == "must" for m in fed), "should": sum(m["priority"] == "should" for m in fed),
                               "score": imp, "measures": [{"id": m["id"], "name": m["name"], "priority": m["priority"]} for m in fed]},
                    "readiness": {"count": k, "of": FULL, "score": rdy, "checks": checks}, "zone": z,
                    "draft": _draft(z)})
    return {"available": True, "baseline_id": bid, "sources": out, "left_out": left, "restricted": hidden,
            "thresholds": {"full": FULL, "high_from": FULL // 2, "ready_from": FULL // 2}}


def _draft(z: str) -> dict:
    """Lens's draft, from the position alone: it matters (high impact) so it is strategic; where it is not ready, that is the work to do."""
    if z == "p1":
        return {"strategic": True, "reason": "It feeds Must or Should measures and is ready to scan."}
    if z == "unknown":
        return {"strategic": True, "reason": "It feeds Must or Should measures but is not ready yet: close the gaps first."}
    return {"strategic": False, "reason": "It feeds few Must or Should measures."}


# ---- the file ---------------------------------------------------------------------------------------------------------------------

def build_file(plane, intent: dict, stored: dict | None, now: str, confirm: dict | None = None) -> dict:
    """The whole file from the records and any earlier confirmations. `confirm` is {source_id, strategic, reason, by} for one new one."""
    pos = positions(plane, intent)
    old = (stored or {}).get("sources") or {}
    sources = {}
    for s in pos["sources"]:
        sid, prev = s["id"], old.get(s["id"]) or {}
        cl = prev.get("classification")
        if confirm and confirm["source_id"] == sid:
            cl = _cell({"strategic": confirm["strategic"]}, "stated", confirm["by"], "confirmed in the source map", now, reason=confirm["reason"], zone=s["zone"])
        elif not cl or cl.get("mark") != "stated":
            cl = _cell({"strategic": s["draft"]["strategic"]}, "guessed", "Lens", f"position: zone {s['zone']}", now, reason=s["draft"]["reason"], zone=s["zone"])
        src = "catalogue.json, kpis.json"
        sources[sid] = {"name": s["name"], "restricted": s["restricted"], "zone": s["zone"],
                        "impact": _cell({k: s["impact"][k] for k in ("count", "must", "should", "score")}, "stated", "Signal Harbor", src, now),
                        "readiness": _cell({"count": s["readiness"]["count"], "of": FULL, "score": s["readiness"]["score"],
                                            "checks": {c["key"]: c["ok"] for c in s["readiness"]["checks"]}}, "stated", "Signal Harbor", src, now),
                        "classification": cl}
    return {"version": 1, "intent_id": intent["id"], "baseline_id": pos.get("baseline_id"), "computed_at": now, "sources": sources}


def _view(plane, intent: dict, viewer) -> dict:
    pos = positions(plane, intent, viewer)
    stored = ((read_map(plane, intent["id"]) or {}).get("sources")) or {}
    for s in pos["sources"]:
        if s["silhouette"]:
            continue
        cl = (stored.get(s["id"]) or {}).get("classification")
        s["classification"] = ({"strategic": cl["value"]["strategic"], "reason": cl.get("reason", ""), "mark": cl["mark"], "by": cl["by"], "at": cl["at"],
                                "moved_since": cl["mark"] == "stated" and cl.get("zone") not in (None, s["zone"])}
                               if cl else {"strategic": s["draft"]["strategic"], "reason": s["draft"]["reason"], "mark": "guessed", "by": "Lens", "at": None,
                                           "moved_since": False})
    pos["written"] = bool(stored)
    pos["zones"] = ZONES
    pos["can_confirm"] = bool({"analyst", "company_admin"} & viewer.roles)
    return pos


def _seen(plane, viewer, intent_id) -> dict:
    rec = S.read_intent(plane, intent_id) if intent_id else None
    if rec is None or S.tier_of(rec, viewer, S.areas_of(plane, viewer)) != "content":
        raise LookupError(intent_id)
    return rec


def _run(request: Request, fn):
    try:
        plane, viewer = _plane(request), _viewer(request)
        return JSONResponse(fn(plane, viewer))
    except LookupError:
        return JSONResponse({"detail": S.NOT_FOUND}, status_code=404)
    except (PermissionError, CrossCompanyError):
        return JSONResponse({"detail": "You cannot do that."}, status_code=403)
    except ValueError as e:
        return JSONResponse({"detail": str(e) or "That is not valid."}, status_code=400)
    except S.Unreadable:
        return JSONResponse({"detail": S.UNREADABLE}, status_code=500)


@router.get("/api/intents/sources/map")
def get_source_map(request: Request, intent_id: str = ""):
    return _run(request, lambda plane, viewer: _view(plane, _seen(plane, viewer, intent_id), viewer))


@router.post("/api/intents/sources/map")
def post_source_map(request: Request, intent_id: str = "", body: dict = Body(default={})):
    """No `source_id`: Lens drafts the map and the file is written (a person's confirmation is kept). With `source_id`, `strategic` and a
    `reason`: the analyst or organiser confirms that one source."""
    def go(plane, viewer):
        rec = _seen(plane, viewer, intent_id)
        if not isinstance(body, dict):
            raise ValueError("Please send the details as a JSON object.")
        confirm = None
        if body.get("source_id") is not None:
            sid, reason = str(body["source_id"]), str(body.get("reason") or "").strip()
            if not isinstance(body.get("strategic"), bool):
                raise ValueError("Please say whether it is strategic or not.")
            if not REASON_MIN <= len(reason) <= REASON_MAX:
                raise ValueError("Please give a reason, in a sentence.")
            if not any(s["id"] == sid and not s["silhouette"] for s in positions(plane, rec, viewer)["sources"]):
                raise LookupError(sid)
            if not viewer.account_id:
                raise PermissionError
            confirm = {"source_id": sid, "strategic": body["strategic"], "reason": reason, "by": viewer.name or "Unnamed"}
        with lock_for(plane.path("intents", intent_id)):
            write_json_atomic(file_of(plane, intent_id), build_file(plane, rec, read_map(plane, intent_id), S.now_iso(), confirm))
        return _view(plane, rec, viewer)
    return _run(request, go)
