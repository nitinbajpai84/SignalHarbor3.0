"""Spec 55: the data knowledge map. The map is a projection (`sh_platform/graph/knowledge_map.py`); this file serves what the gated graph route
does not carry: scan results, owner kinds, the last update, the owner's two buttons, the scan, and the systems to connect.

Everything is read through `graph_for` (the viewer's own gated graph), so a restricted thing is never named here. Routes sit under
`/api/intents/knowledge-map/` (open questions 1 and 2: the scan's confirm and reject are served here, not under m3_connect).
"""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, HTTPException, Query, Request

from sh_platform.graph import knowledge_map as km
from sh_platform.graph.hooks import mark_dirty, rebuild_if_dirty
from sh_platform.graph.read import graph_for
from sh_platform.graph.versions import append_version
from sh_platform.intents import _plane, _viewer
from sh_platform.jsonfile import read_json_strict
from sh_platform.profile.view import norm

log = logging.getLogger(__name__)
router = APIRouter()
km.install_scan_hook()  # every file module 3 profiles is a scan run: an update moment
SHUT = "Your company space could not be opened. Please ask your administrator."
FEWER = "Fewer than five"
RESULT_WORDS = {"available": "Available", "missing": "Missing", "found_elsewhere": "Found elsewhere"}


def _open(request: Request):
    try:
        plane, viewer = _plane(request), _viewer(request)
    except PermissionError:
        raise HTTPException(403, SHUT) from None
    rebuild_if_dirty(plane)
    km.try_backfill(plane)  # the seeded charter, gap report, blueprint and release predate the map
    return plane, viewer


def _raw(plane) -> dict:
    try:
        return read_json_strict(plane.path("graph", "company.json"), dict) or {}
    except (OSError, ValueError):
        return {}


def _seen(plane, viewer) -> tuple[dict, dict]:
    """(raw nodes the viewer sees by id, raw doc). A silhouette is not seen."""
    g = graph_for(plane, viewer)
    ok = {n["id"] for n in g["nodes"] if not n.get("restricted")}
    doc = _raw(plane)
    return {n["id"]: n for n in doc.get("nodes", []) if n["id"] in ok}, doc


def _owners_of(doc: dict, seen: dict, nid: str) -> list[dict]:
    return [{"id": e["to"], "label": seen[e["to"]]["label"], "kinds": e.get("owner_kind") or []}
            for e in doc.get("edges", []) if e["type"] == "owned_by" and e["from"] == nid and e["to"] in seen]


def _decider(doc: dict, seen: dict, nid: str, viewer) -> bool:
    """The named source owner of the field: owner kind source, else the data owner while no source owner is named (spec 28 seeds it that way)."""
    own = _owners_of(doc, seen, nid)
    named = [o for o in own if "source" in o["kinds"]] or [o for o in own if "data" in o["kinds"]]
    return any(norm(o["label"]) == norm(viewer.name) and not viewer.shared_name for o in named)


def _latest(plane, viewer) -> dict | None:
    rows = km.read_updates(plane)
    return rows[-1] if rows else None


def overview(plane, viewer, now: datetime | None = None) -> dict:
    """What the Map and the node page add: the last update (the line built from what this viewer sees), scan results, owner kinds, who may decide."""
    now = now or datetime.now(timezone.utc)
    seen, doc = _seen(plane, viewer)
    aid = km.newest_assessment(plane)
    rows = km.newest_by_node(km.verify_rows(plane, aid))
    checks = {}
    for e in doc.get("edges", []):
        if e["type"] != "verified_by" or e["from"] not in seen or e["to"] not in seen:
            continue
        where = e.get("found_in")
        checks[e["from"]] = {
            "result": e.get("result"), "word": RESULT_WORDS.get(e.get("result"), ""), "scanned_at": e.get("scanned_at"), "claimed": e.get("claimed"),
            "found_in": ({"id": where, "label": seen[where]["label"]} if where in seen else None) if e.get("result") == "found_elsewhere" else None,
            "confirmed_by": e.get("confirmed_by"), "rejected_by": e.get("rejected_by"), "gap_report": e["to"], "assessment": aid,
            "can_decide": e.get("result") == "found_elsewhere" and not e.get("confirmed_by") and _decider(doc, seen, e["from"], viewer)}
    last = _latest(plane, viewer)
    out_last = None
    if last:
        ids = [i for i in last.get("added_ids") or [] if i in seen]
        counts: dict[str, int] = {}
        for i in ids:
            counts[seen[i]["type"]] = counts.get(seen[i]["type"], 0) + 1
        line = km.line_for(last["moment"], last["by"], counts)
        if last["moment"] == "scan_run" and checks:  # the scan's line counts only the results this viewer sees
            tally = {r: sum(1 for c in checks.values() if c["result"] == r) for r in RESULT_WORDS}
            line = (f"The scan checked {len(checks)} data point{'' if len(checks) == 1 else 's'}: " +
                    ", ".join(f"{n} {RESULT_WORDS[r].lower()}" for r, n in tally.items() if n))
        out_last = {"id": last["id"], "moment": last["moment"], "by": last["by"], "at": last["at"], "line": line}
    week = sum(1 for r in km.read_updates(plane) if _age(r.get("at"), now) < timedelta(days=7))
    return {"last_update": out_last, "updates_this_week": week, "checks": checks, "scan_rows": len(rows) if rows else 0,
            "owners": {nid: _owners_of(doc, seen, nid) for nid in seen if seen[nid]["type"] in ("Field", "Source", "File", "Mart", "System", "Measure")}}


def _age(at, now: datetime) -> timedelta:
    try:
        t = datetime.fromisoformat(str(at))
    except ValueError:
        return timedelta.max
    return now - (t if t.tzinfo else t.replace(tzinfo=timezone.utc))


@router.get("/api/intents/knowledge-map/overview")
def get_overview(request: Request) -> dict:
    plane, viewer = _open(request)
    return overview(plane, viewer)


def answer(plane, viewer, node: str, reason: str | None) -> dict:
    """Confirm (reason None) or reject a 'found elsewhere' result. Only the named source owner; 404 for a node the viewer does not see."""
    seen, doc = _seen(plane, viewer)
    if node not in seen:
        raise HTTPException(404, "No such node")
    if not _decider(doc, seen, node, viewer):
        raise HTTPException(403, "Only the source owner of this field can answer this.")
    if reason is not None and not reason.strip():
        raise HTTPException(422, "Say why this is not the same thing.")
    aid = km.newest_assessment(plane)
    row = km.decide(plane, aid, node, viewer.name, None if reason is None else reason.strip())
    if row is None:
        raise HTTPException(409, "There is nothing to answer here: this was not found elsewhere, or it has been answered.")
    found = next((e.get("found_in") for e in doc["edges"] if e["from"] == node and e["type"] == "verified_by"), None)
    where = seen[found]["label"] if found in seen else "another system"
    append_version(plane, node, (f"Found in {where}, confirmed by {viewer.name}" if reason is None else f"Not the same as the field found in {where}: {viewer.name} said so"),
                   viewer.name, aid)
    mark_dirty(plane)
    rebuild_if_dirty(plane)
    return {"node": node, "result": km.effective(row), "confirmed_by": row.get("confirmed_by"), "rejected_by": row.get("rejected_by")}


@router.post("/api/intents/knowledge-map/{node_id}/confirm")
def post_confirm(request: Request, node_id: str) -> dict:
    plane, viewer = _open(request)
    return answer(plane, viewer, node_id, None)


@router.post("/api/intents/knowledge-map/{node_id}/reject")
def post_reject(request: Request, node_id: str, body: dict = Body(...)) -> dict:
    plane, viewer = _open(request)
    return answer(plane, viewer, node_id, str(body.get("reason") or ""))


@router.post("/api/intents/knowledge-map/scan")
def post_scan(request: Request, body: dict = Body(default={})) -> dict:
    """Runs the scan on the newest assessment (module 3's scan step calls `km.scan_assessment` itself once wired; see Shared files needed)."""
    plane, viewer = _open(request)
    aid = km.newest_assessment(plane)
    if not aid:
        raise HTTPException(409, "There is no gap analysis to scan yet.")
    counts = km.scan_assessment(plane, aid, viewer.name)
    km.try_moment(plane, "scan_run", aid, viewer.name)
    return counts


def systems_to_connect(plane, viewer) -> dict:
    """Build room 0, "Systems to connect, from the map": from each measure a charter problem asked for, along `fed_by` and `held_in` to the systems.
    A restricted system is one row with counts only ("Fewer than five" below five)."""
    seen, doc = _seen(plane, viewer)
    ids = {n["id"]: n for n in doc.get("nodes", [])}
    edges = doc.get("edges", [])
    measures = {e["to"] for e in edges if e["type"] == "measured_by" and e["to"] in seen}
    feeds = {m: [e["to"] for e in edges if e["from"] == m and e["type"] == "fed_by"] for m in measures}
    held = {}
    for e in edges:
        if e["type"] == "held_in":
            held.setdefault(e["from"], e["to"])
    for e in edges:  # a mart or pipeline: where its pipeline lands
        if e["type"] == "lands_at":
            held.setdefault(e["from"], e["to"])
    found = {e["found_in"] for e in edges if e["type"] == "verified_by" and e.get("result") == "found_elsewhere" and e.get("found_in")}
    rows: dict[str, dict] = {}
    for m, targets in feeds.items():
        for t in targets:
            sysid = held.get(t) or (t if ids.get(t, {}).get("type") == "System" else None)
            if not sysid or (t not in seen and sysid in seen):  # a hidden source never adds to an open system's counts
                continue
            r = rows.setdefault(sysid, {"measures": set(), "fields": set(), "said": 0})
            r["measures"].add(m)
            r["fields"].update(e["to"] for e in edges if e["from"] == t and e["type"] == "uses")
    out = []
    for sysid, r in sorted(rows.items(), key=lambda kv: (kv[0] not in seen, ids[kv[0]]["label"].lower())):
        shown = sysid in seen
        ms, fs = len(r["measures"]), len(r["fields"])
        owner = next((o["label"] for o in _owners_of(doc, seen, sysid) if shown), None)
        out.append({"id": sysid if shown else None, "label": ids[sysid]["label"] if shown else "A restricted system", "owner": owner,
                    "measures": ms if shown or ms >= 5 else FEWER, "fields": fs if shown or fs >= 5 else FEWER, "found_by_scan": sysid in found})
    n, scan = len(out), sum(1 for o in out if o["found_by_scan"])
    line = (f"The charter's measures need data from {n} system{'' if n == 1 else 's'}."
            + (f" {scan} {'was' if scan == 1 else 'were'} found by the last scan." if scan else "")) if n else \
        "The map does not yet say where these measures' data lives. Ask the source owners."
    return {"line": line, "systems": out}


@router.get("/api/intents/knowledge-map/systems-to-connect")
def get_systems_to_connect(request: Request, from_: str = Query("", alias="from")) -> dict:
    plane, viewer = _open(request)
    return systems_to_connect(plane, viewer)


def pulse_lines(plane, viewer, now: datetime) -> list[dict]:
    """The two Pulse lines (spec 55): "What changed in the map" (inform, for anyone who may see the map; never the super admin) and
    "One field you own was found in another system" (decision, to the source owner). Same shape as `pulse.lines.line`; `minutes` is given here
    because the Pulse table has no `inform` kind (see Shared files needed)."""
    if "super_admin" in viewer.roles:
        return []
    out = []
    ov = overview(plane, viewer, now)
    last = ov["last_update"]
    if last and _age(last["at"], now) < timedelta(days=7):
        out.append({"id": f"map:{last['id']}", "kind": "inform", "title": "What changed in the map", "detail": last["line"], "href": "/centre/intent/graph?view=fresh",
                    "action": "See what changed", "minutes": 1, "due": None, "source": {"record": "graph/updates.json", "at": last["at"]}})
    for nid, c in ov["checks"].items():
        if c["can_decide"]:
            where = (c["found_in"] or {}).get("label") or "another system"
            out.append({"id": f"map:found:{nid}", "kind": "decision", "title": "One field you own was found in another system",
                        "detail": f"Said missing; found in {where}. Is it the same thing?", "href": f"/centre/intent/map/{nid}", "action": "Confirm or reject",
                        "minutes": 3, "due": None, "source": {"record": "intents/m3_connect/verify", "at": c["scanned_at"]}})
    return out
