"""M1 routes: the company map for every signed-in role (read-only), "Something looks wrong" notes on any node, the open notes for the
decision maker's Home, and a phrase lookup for the agents.

GET  /api/v1/map                         the viewer's gated map (graph.read.graph_for), each open node with where it came from and its notes
GET  /api/v1/map/ask?q=                  nodes matching a phrase: names and definitions only, never rows
POST /api/v1/map/node/{node_id}/comments {text}: a note on a node, in graph/comments.json (the 2.0 file, keyed by node)
GET  /api/v1/map/comments                the open notes
POST /api/v1/map/comments/{cid}/seen     the decision maker marks a note seen
Data stays in the signed-in company's plane: every path comes from `_plane(request)`."""
import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Body, HTTPException, Request

from sh_platform.graph.hooks import rebuild_if_dirty
from sh_platform.graph.read import graph_for
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1 import m1_map
from sh_platform.v1.seats import DECISION_MAKER, NO_SPACE, require_seat

router = APIRouter()
log = logging.getLogger(__name__)
INFO = ("what", "said_by", "from_file", "from_record", "at", "intents", "state", "roles", "definition", "formula", "unit", "period", "status",
        "code", "layer", "manual", "stub", "read", "quote", "readers", "decisions", "needed_by", "frequency", "audience", "answer", "kind",
        "loaded", "link", "field_type", "example", "inputs", "outputs", "comparisons", "filters")
MAX_TEXT = 1000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _open(request: Request):
    from sh_platform.profile.api import _plane, _viewer
    try:
        plane, viewer = _plane(request), _viewer(request)
    except PermissionError:
        raise HTTPException(403, {"error": "forbidden", "message": NO_SPACE}) from None
    rebuild_if_dirty(plane)
    return plane, viewer


def _comments(plane) -> dict:
    try:
        return read_json_strict(plane.path("graph", "comments.json"), dict) or {}
    except (OSError, ValueError):
        return {}


def _map(plane, viewer) -> dict:
    """The viewer's gated map; an open node gains its origin and its notes from the raw build (a silhouette gains nothing)."""
    g = graph_for(plane, viewer)
    raw = {n["id"]: n for n in (read_json_strict(plane.path("graph", "company.json"), dict) or {}).get("nodes", [])}
    notes = _comments(plane)
    nodes = []
    for n in g["nodes"]:
        if n.get("restricted"):
            nodes.append(n)
            continue
        r = raw.get(n["id"], {})
        nodes.append({**n, **{k: r[k] for k in INFO if k in r},
                      "notes": [{k: c.get(k) for k in ("id", "text", "by", "at", "state")} for c in notes.get(n["id"], []) if isinstance(c, dict)]})
    try:  # K2: an Internal project's definition text is its team's (G1's artefact rule)
        from sh_platform.v1 import k2_map
        k2_map.gate_nodes(plane, viewer, nodes, raw)
    except Exception:  # noqa: BLE001 - never a broken map; the nodes were gated by the graph already
        log.warning("the definitions on the map could not be gated")
        nodes = [n for n in nodes if n.get("type") not in ("Definition", "Concept") or n.get("restricted")]
    return {"built_at": g["built_at"], "nodes": nodes, "edges": g["edges"]}


@router.get("/api/v1/map")
def get_map(request: Request) -> dict:
    return _map(*_open(request))


@router.get("/api/v1/map/ask")
def get_ask(request: Request, q: str = "") -> dict:
    plane, viewer = _open(request)
    from sh_platform.v1 import k2_map  # K2: the concept, its variants and who owns each, from names and definitions only
    return {"q": q, "nodes": m1_map.ask(_map(plane, viewer)["nodes"], q[:200]), "concepts": k2_map.answer(plane, viewer, q[:200])}


@router.post("/api/v1/map/node/{node_id}/comments")
def post_comment(request: Request, node_id: str, body: dict = Body(...)) -> dict:
    plane, viewer = _open(request)
    if not any(n["id"] == node_id and not n.get("restricted") for n in graph_for(plane, viewer)["nodes"]):
        raise HTTPException(404, "No such thing on the map")
    text = str(body.get("text") or "").strip()
    if not text or len(text) > MAX_TEXT:
        raise HTTPException(400, "Write what looks wrong, up to 1000 characters")
    item = {"id": secrets.token_hex(6), "kind": "comment", "node": node_id, "text": text, "by": viewer.name or "Someone", "at": _now(), "state": "open"}
    path = plane.path("graph", "comments.json")
    with lock_for(path):
        doc = _comments(plane)
        doc.setdefault(node_id, []).append(item)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(path, doc)
    return item


@router.get("/api/v1/map/comments")
def get_comments(request: Request) -> dict:
    plane, viewer = _open(request)
    seen = {n["id"]: n["label"] for n in graph_for(plane, viewer)["nodes"] if not n.get("restricted")}
    out = [{**c, "node": nid, "label": seen[nid]} for nid, items in _comments(plane).items() if nid in seen
           for c in items if isinstance(c, dict) and c.get("state") == "open"]
    return {"comments": sorted(out, key=lambda c: str(c.get("at")), reverse=True)}


@router.post("/api/v1/map/comments/{cid}/seen")
def post_seen(request: Request, cid: str) -> dict:
    require_seat(request, DECISION_MAKER)
    plane, _ = _open(request)
    path = plane.path("graph", "comments.json")
    with lock_for(path):
        doc = _comments(plane)
        item = next((c for items in doc.values() for c in items if isinstance(c, dict) and c.get("id") == cid), None)
        if item is None:
            raise HTTPException(404, "No such note")
        item["state"] = "seen"
        write_json_atomic(path, doc)
    return item
