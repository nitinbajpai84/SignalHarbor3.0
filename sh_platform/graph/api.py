"""`GET /api/company/graph?view=map|trace|holes|lineage&focus=<node id>`: the viewer's own gated graph (`read.graph_for`, the profile's Viewer), labels only.

map: every node and edge the viewer may see. trace: the focus node and everything downstream of it (a Measure to its Source, Field, Process and
owner). holes: the Measures with no Source. An unknown focus (also another company's id) is 404; a silhouette id is a node like any other.

The map view also carries the five columns of the Graph artboard (walls, problems, measures, systems, owners: ids only), `by_wall` (the
problems and measures each held wall produced, through its signed charter's problem ids), `new_this_week` (the column things with a version under seven days old, the one list the chip, the columns and the panel share),
`new_detail` (their versions of the week), `holes` (measure ids with no source) and `summary` counts. A wall is labelled by its topic, else its purpose; the
session files and charter outcomes are read by path, never imported from module 1."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request

from sh_platform.graph.build import _newest_baseline, _read
from sh_platform.graph.hooks import rebuild_if_dirty
from sh_platform.graph.knowledge_map import lineage
from sh_platform.graph.read import graph_for, summary
from sh_platform.graph.versions import wall_name
from sh_platform.jsonfile import read_json_strict
from sh_platform.plane import CompanyPlane
from sh_platform.profile.api import _plane, _viewer

router = APIRouter()
VIEWS = ("map", "trace", "holes", "lineage")


def _trace(g: dict, focus: str) -> dict:
    if focus not in {n["id"] for n in g["nodes"]}:
        raise HTTPException(404, "No such node")
    seen, todo = {focus}, [focus]
    while todo:
        cur = todo.pop()
        for e in g["edges"]:
            if e["from"] == cur and e["to"] not in seen:
                seen.add(e["to"])
                todo.append(e["to"])
    return {**g, "nodes": [n for n in g["nodes"] if n["id"] in seen], "edges": [e for e in g["edges"] if e["from"] in seen and e["to"] in seen]}


COLUMN_TYPES = {"problems": ("Problem",), "measures": ("Measure",), "systems": ("System", "Source"), "owners": ("Person",)}
WEEK = timedelta(days=7)


def _files(plane: CompanyPlane, *parts: str) -> list[dict]:
    folder = plane.path(*parts)
    return [d for f in sorted(folder.glob("*.json") if folder.is_dir() else []) if (d := _read(plane, *parts, f.name))]


def _new_ids(plane: CompanyPlane, nodes: list[dict], now: datetime) -> dict[str, list[dict]]:
    """The one source of "new this week": for each node the viewer sees as a column thing (not a silhouette, card or pipeline), the versions
    dated within the last seven days, newest first. A node is new when it has any; its older history does not matter."""
    try:
        versions = read_json_strict(plane.path("graph", "versions.json"), dict) or {}
    except (OSError, ValueError):
        return {}
    kinds = {t for ts in COLUMN_TYPES.values() for t in ts}
    out: dict[str, list[dict]] = {}
    for n in nodes:
        rows = versions.get(n["id"])
        if n["type"] not in kinds or n.get("restricted") or not isinstance(rows, list):
            continue
        week = []
        for r in rows:
            try:
                at = datetime.fromisoformat(str(r.get("at"))) if isinstance(r, dict) else None
            except ValueError:
                at = None
            if at and at.tzinfo and timedelta(0) <= now - at < WEEK:
                week.append({"what": str(r.get("what") or ""), "by": str(r.get("by") or ""), "at": str(r["at"])})
        if week:
            out[n["id"]] = sorted(week, key=lambda w: w["at"], reverse=True)
    return out


def _map_extras(plane: CompanyPlane, g: dict, now: datetime, account_id: str | None = None) -> dict:
    ids = {n["id"] for n in g["nodes"]}
    charters = [c for c in _files(plane, "intents", "m1_intent", "outcomes") if c.get("kind") == "charter"]
    signed = {str(c.get("session_id")) for c in charters if c.get("signed_at")}
    walls = []
    for s in _files(plane, "intents", "m1_intent", "sessions"):
        prep = s.get("preparation") if isinstance(s.get("preparation"), dict) else {}
        label = " ".join(str(prep.get("topic") or prep.get("purpose") or "").split())[:80]
        if s.get("id") and s.get("state") != "draft" and label:
            walls.append({"id": f"wall:{s['id']}", "label": wall_name(plane, s, str(s["id"]) in signed, account_id, label), "session": str(s["id"])})
    measured: dict[str, set[str]] = {}
    for e in g["edges"]:
        if e["type"] == "measured_by":
            measured.setdefault(e["from"], set()).add(e["to"])
    by_wall = []
    for w in walls:
        probs = sorted({f"problem:{p['id']}" for c in charters if c.get("session_id") == w["session"]
                        for p in c.get("problems") or [] if isinstance(p, dict) and f"problem:{p.get('id')}" in ids})
        by_wall.append({"wall": w["id"], "problems": probs, "measures": sorted({m for p in probs for m in measured.get(p, ())})})
    columns: dict[str, list] = {"walls": [{"id": w["id"], "label": w["label"]} for w in walls]}
    for col, types in COLUMN_TYPES.items():
        columns[col] = [n["id"] for n in g["nodes"] if n["type"] in types]
    fed = {e["from"] for e in g["edges"] if e["type"] == "fed_by"}
    holes = [n["id"] for n in g["nodes"] if n["type"] == "Measure" and not n.get("restricted") and n["id"] not in fed]
    new = _new_ids(plane, g["nodes"], now)
    return {"columns": columns, "by_wall": by_wall, "new_this_week": sorted(new), "new_detail": new, "holes": holes,
            "summary": {"things": len(g["nodes"]) + len(walls), "links": len(g["edges"]) + sum(len(b["problems"]) for b in by_wall),
                        "walls": len(walls), "charters": len(charters), "baselines": 1 if _newest_baseline(plane) else 0}}


@router.get("/api/company/graph")
def company_graph(request: Request, view: str = "map", focus: str = "") -> dict:
    if view not in VIEWS:
        raise HTTPException(400, "Unknown view")
    try:
        plane, viewer = _plane(request), _viewer(request)
    except PermissionError:
        raise HTTPException(403, "Your company space could not be opened. Please ask your administrator.") from None
    rebuild_if_dirty(plane)  # a restriction tightened since the last build must apply now, never the older, more open file
    g = graph_for(plane, viewer)
    if view == "trace":
        g = _trace(g, focus)
    if view == "lineage":  # spec 55: upstream and downstream of the focus only
        g = lineage(g, focus)
        if g is None:
            raise HTTPException(404, "No such node")
    if view == "holes":
        holes = summary(plane, viewer)["holes"]["measure_no_source"]
        ids = {h["id"] for h in holes}
        return {"view": view, "version": g["version"], "built_at": g["built_at"], "nodes": [n for n in g["nodes"] if n["id"] in ids], "edges": [], "holes": holes}
    return {"view": view, **g, **(_map_extras(plane, g, datetime.now(timezone.utc), request.state.account_id) if view == "map" else {})}
