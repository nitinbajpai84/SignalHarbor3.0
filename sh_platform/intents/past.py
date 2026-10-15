"""IC v2 (12): past intents and history. The list is counted on the server from `intents/<id>/intent.json` for the intents the viewer
may see (store.tier_of); drafts never appear. The chain itself is file 20's walk (links.chain).

`closed_month` and `search_text` are derived on read (12 says rebuilt if missing), so nothing extra is stored on the record.
A correction after closing is a history row plus a `note_added` event; a share request is a `share_requested` event.
"""
import re
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.intents import _plane, _viewer
from sh_platform.intents import lifecycle as L
from sh_platform.intents import links as K
from sh_platform.intents import store as S
from sh_platform.profile import view as pview

router = APIRouter()

WINDOW_MONTHS = 12   # 12 open question 1: the default window and the step of "Show older months"
LINE_CHARS = 140     # 12 open question 1: the one-liner length
OUTCOMES = {"initiative": "Became an initiative", "backlog": "Went to backlog", "problem": "Became a problem", "nothing": "Nothing came of it",
            "decision_made": "Decision made", "cancelled": "Cancelled"}
TYPE_NAMES = {"initiative": "Initiative", "brainstorm": "Brainstorm", "pulse": "Weekly check-in", "problem": "Problem", "decision": "Decision"}
ROLE_NAMES = {"organiser": "Organiser", "sponsor": "Sponsor", "decider": "Decider", "owner": "Owner", "reporter": "Reporter",
              "participants": "Participant", "advisers": "Participant", "affected": "Affected", "observers": "Observer"}
RUNNING = ("draft", "open", "in_session", "closing")


def closed_month(rec: dict, tz) -> str | None:
    at = (rec.get("closure") or {}).get("closed_at")
    if rec["state"] not in ("closed", "cancelled") or not at:
        return None
    try:
        return datetime.fromisoformat(str(at).replace("Z", "+00:00")).astimezone(tz).strftime("%Y-%m")
    except ValueError:
        return str(at)[:7]


def search_text(rec: dict) -> str:
    return f"{rec.get('title', '')} {rec.get('purpose', '')}".lower()


def outcome_keys(rec: dict) -> set[str]:
    if rec["state"] == "cancelled":
        return {"cancelled"}
    keys = {n.get("kind") for n in (rec.get("closure") or {}).get("next") or []} & {"initiative", "backlog", "problem", "nothing"}
    return keys | ({"decision_made"} if rec["type"] == "decision" else set())


def role_of(rec: dict, viewer: pview.Viewer) -> str | None:
    p = rec.get("people") or {}
    for slot in S.SLOTS:
        if S._named(p.get(slot), viewer):
            return ROLE_NAMES[slot]
    return next((ROLE_NAMES[k] for k in S.LISTS if any(S._named(x, viewer) for x in p.get(k) or [])), None)


def card(rec: dict, tier: str, viewer: pview.Viewer, title_of, tz) -> dict:
    """Screen B, the closed card, at the viewer's tier. `title_of(id)` gives a target's title or None when the viewer may not see it."""
    c, p = rec.get("closure") or {}, rec.get("people") or {}
    nxt = []
    for n in c.get("next") or []:
        kind, ref = n.get("kind"), n.get("ref")
        if kind in ("nothing", "handled"):
            nxt.append({"kind": kind, "label": f"Nothing, because {n.get('reason') or 'no reason recorded'}" if kind == "nothing" else "Handled",
                        "ref": None})
        elif kind == "backlog":
            nxt.append({"kind": kind, "label": "Backlog", "ref": ref})
        else:
            t = title_of(ref) if ref else None
            nxt.append({"kind": kind, "ref": ref if t else None,
                        "label": f"{kind.capitalize()}: {t}" if t else "Restricted" if ref else f"{kind.capitalize()}: not started"})
    scores = [r["score"] for r in rec.get("ratings") or [] if isinstance(r.get("score"), int)]
    rated = rec["type"] != "pulse" and len(scores) >= 3
    count = (1 if p.get("organiser") else 0) + len(p.get("participants") or [])
    return {"id": rec["id"], "type": rec["type"], "title": rec.get("title", ""), "purpose": rec.get("purpose", ""), "areas": rec.get("areas") or [],
            "state": rec["state"], "opened": rec.get("created_at"), "closed_at": c.get("closed_at"), "closed_month": closed_month(rec, tz),
            "organiser": (p.get("organiser") or {}).get("name") or None, "people_count": count,
            "outcome_line": K._first_sentence(c.get("what_came_out"), LINE_CHARS) if rec["state"] == "closed" else "",
            "cancel_reason": (c.get("cancel_reason") or "No reason recorded") if rec["state"] == "cancelled" else None,
            "next": nxt, "rating": {"avg": round(sum(scores) / len(scores), 1), "n": len(scores)} if rated else None,
            "tier": tier, "role": role_of(rec, viewer), "time_box_ends": (rec.get("time_box") or {}).get("ends")}


def _quarter(month: str) -> str:
    y, m = month.split("-")
    return f"{y} Q{(int(m) - 1) // 3 + 1}"


def counters(cards: list[dict], viewer: pview.Viewer, recs: dict, title_of, total_differs: bool) -> dict:
    closed = [c for c in cards if c["state"] == "closed"]
    used = [c for c in closed if any(n["kind"] in ("initiative", "backlog", "problem") for n in c["next"])]
    targets = [n["ref"] for c in used for n in c["next"] if n["kind"] in ("initiative", "problem") and n["ref"]]
    live = sum(1 for t in targets if t in recs and recs[t]["state"] in RUNNING)
    done = sum(1 for t in targets if t in recs and (recs[t]["state"] == "closed" or (recs[t].get("links") or {}).get("build")))
    per_q: dict[str, dict] = {}
    for c in cards:
        if c["closed_month"]:
            q = per_q.setdefault(_quarter(c["closed_month"]), {})
            q[c["type"]] = q.get(c["type"], 0) + 1
    rated = [c["rating"]["avg"] for c in cards if c["rating"]]
    return {"per_quarter": per_q, "outcomes_used": {"used": len(used), "closed": len(closed)},
            "targets": {"running": live, "done": done, "total": len(targets)},
            "cancelled": sum(c["state"] == "cancelled" for c in cards),
            "closed_with_nothing": sum(1 for c in closed if c["next"] and all(n["kind"] == "nothing" for n in c["next"])),
            "average_rating": round(sum(rated) / len(rated), 1) if rated else None, "mine": sum(1 for c in cards if c["role"]),
            "partial": total_differs}


def past_list(plane, viewer: pview.Viewer, q: dict) -> dict:
    """Screen A (and E with mine=1): cards, month groups, chips with counts, counters. Every filter is applied on the server."""
    tz, areas = L.company_zone(plane), S.areas_of(plane, viewer)
    recs: dict[str, dict] = {}
    for row in S.read_index(plane):
        try:
            rec = S.read_intent(plane, row["id"])
        except S.Unreadable:
            continue
        if rec:
            recs[rec["id"]] = rec
    tiers = {i: t for i, r in recs.items() if (t := S.tier_of(r, viewer, areas))}

    def title_of(i):
        return recs[i].get("title") if i in tiers else None
    from sh_platform.intents.home import _proving_fields  # spec 58 chip (C20)
    all_past = [{**card(recs[i], t, viewer, title_of, tz), **_proving_fields(plane, i)} for i, t in tiers.items() if recs[i]["state"] in ("closed", "cancelled")]
    mine = q.get("mine") == "1"
    term = " ".join(str(q.get("q") or "").lower().split())[:100]
    types = [t for t in (q.get("type") or "").split(",") if t in TYPE_NAMES]
    outs = [o for o in (q.get("outcome") or "").split(",") if o in OUTCOMES]
    frm, to, area = q.get("from") or "", q.get("to") or "", q.get("area") or ""
    month_ok = re.compile(r"\d{4}-\d{2}")
    frm, to = (frm if month_ok.fullmatch(frm) else ""), (to if month_ok.fullmatch(to) else "")

    def base(c):  # area, range, mine and search: the scope the chips and counters count in
        return ((not area or pview.norm(area) in {pview.norm(a) for a in c["areas"]}) and (not frm or (c["closed_month"] or "") >= frm)
                and (not to or (c["closed_month"] or "") <= to) and (not mine or c["role"]) and (not term or term in search_text(c)))
    scoped = [c for c in all_past if base(c)]
    shown = [c for c in scoped if (not types or c["type"] in types) and (not outs or outcome_keys(recs[c["id"]]) & set(outs))]
    shown.sort(key=lambda c: c["closed_at"] or "", reverse=True)
    months_all = sorted({c["closed_month"] for c in shown if c["closed_month"]}, reverse=True)
    page = max(1, int(q.get("page") or 1)) if str(q.get("page") or "1").isdigit() else 1
    window = months_all[:WINDOW_MONTHS * page]
    groups = []
    for m in window:
        in_m = [c for c in shown if c["closed_month"] == m]
        bands = {}
        for c in in_m:
            for i, a in enumerate(c["areas"] or ["No area"]):
                bands.setdefault(a, []).append({**c, "also_in": [x for x in c["areas"] if x != a], "first": i == 0})
        groups.append({"month": m, "count": len(in_m), "bands": [{"area": a, "count": len(cs), "cards": cs} for a, cs in sorted(bands.items())]})
    similar = sum(1 for c in all_past if term and term in search_text(c)) if term else 0
    rail = sorted({a for c in all_past for a in c["areas"]})
    mine_first = [a for a in rail if pview.norm(a) in areas] + [a for a in rail if pview.norm(a) not in areas]
    running = [{**card(recs[i], t, viewer, title_of, tz), "role": role_of(recs[i], viewer), **_proving_fields(plane, i)}
               for i, t in tiers.items() if mine and recs[i]["state"] in RUNNING and role_of(recs[i], viewer)]
    admin = pview.ADMIN in viewer.roles
    return {"months": groups, "older": len(months_all) > len(window), "count": len(shown), "any": bool(all_past),
            "areas": [{"area": a, "count": sum(1 for c in all_past if a in c["areas"]), "mine": pview.norm(a) in areas} for a in mine_first],
            "all_count": len(all_past), "tagged": bool(areas) or admin,
            "types": {t: sum(1 for c in scoped if c["type"] == t) for t in TYPE_NAMES},
            "outcomes": {o: sum(1 for c in scoped if o in outcome_keys(recs[c["id"]])) for o in OUTCOMES},
            "counters": counters(scoped, viewer, recs, title_of, not admin and len(tiers) < len(recs)),
            "similar": {"count": similar, "term": term} if similar else None, "running": running,
            "mine_count": sum(1 for i in tiers if role_of(recs[i], viewer) and recs[i]["state"] != "draft")}


# ---- routes ------------------------------------------------------------------------------------------------------------------

@router.get("/api/intents/past")
def get_intents_past(request: Request):
    return past_list(_plane(request), _viewer(request), dict(request.query_params))


@router.get("/api/intents/{intent_id}/chain")
def get_intents_by_intent_id_chain(intent_id: str, request: Request):
    try:
        out = K.chain(_plane(request), _viewer(request), intent_id)
    except S.Unreadable:
        return JSONResponse({"message": S.UNREADABLE}, status_code=409)
    return out if out is not None else JSONResponse({"message": S.NOT_FOUND}, status_code=404)


async def _body(request: Request) -> dict:
    try:
        b = await request.json()
    except ValueError:
        return {}
    return b if isinstance(b, dict) else {}


@router.post("/api/intents/{intent_id}/history-notes")
async def post_intents_by_intent_id_history_notes(intent_id: str, request: Request):
    """"Add a note": the organiser of a closed or cancelled intent adds a later fact. Never replaces closure; a new version row."""
    plane, viewer, body = _plane(request), _viewer(request), await _body(request)
    text = " ".join(str(body.get("text") or "").split())[:1000]
    if not text:
        return JSONResponse({"message": "Write the note first."}, status_code=400)
    with S.locked(plane):
        rec = S.read_intent(plane, intent_id)
        if rec is None or S.tier_of(rec, viewer, S.areas_of(plane, viewer)) is None:
            return JSONResponse({"message": S.NOT_FOUND}, status_code=404)
        if not S._named((rec.get("people") or {}).get("organiser"), viewer):
            return JSONResponse({"message": "Only the organiser can add a note."}, status_code=403)
        if rec["state"] not in ("closed", "cancelled"):
            return JSONResponse({"message": "Notes are added after the intent closes."}, status_code=409)
        rec["history"].append({"at": S.now_iso(), "by": viewer.account_id, "from": rec["state"], "to": rec["state"], "note": text})
        S.write_intent(plane, rec)
    K.note_event(plane, intent_id, "note_added", viewer, None, {"n": len(rec["history"])})
    return {"ok": True, "version": rec["version"]}


@router.post("/api/intents/{intent_id}/share-request")
def post_intents_by_intent_id_share_request(intent_id: str, request: Request):
    """"Ask the organiser to share": a tagged person without content access. One open request per person (read from the events)."""
    plane, viewer = _plane(request), _viewer(request)
    rec = S.read_intent(plane, intent_id)
    tier = S.tier_of(rec, viewer, S.areas_of(plane, viewer)) if rec else None
    if tier is None:
        return JSONResponse({"message": S.NOT_FOUND}, status_code=404)
    if tier != "card":
        return JSONResponse({"message": "You can already read this record." if tier == "content" else "You do not have access to this."},
                            status_code=409 if tier == "content" else 403)
    asked = any(e.get("kind") == "share_requested" and (e.get("by") or {}).get("account") == viewer.account_id
                for e in K.EV.read_events(plane, intent_id))
    if not asked:
        K.note_event(plane, intent_id, "share_requested", viewer, None, {})
    return {"ok": True, "already": asked}
