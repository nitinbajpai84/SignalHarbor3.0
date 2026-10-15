"""Comments, suggestions and ambiguity flags on a map node (SHAPES 10): `graph/comments.json`, newest last.

Anyone who can see the node may read and add. An anonymous item stores "Anonymous" and nothing else about the writer. Only the node's owner
(its `owned_by` person in the graph) or the steward (`graph/steward.json`, else the head of data, else the company admin) decides. An accepted
suggestion appends a version to `graph/versions.json` (a small local writer; the versions module owns the read side)."""
import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from sh_platform.graph.hooks import rebuild_if_dirty
from sh_platform.graph.read import graph_for
from sh_platform.graph.versions import steward
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile import store
from sh_platform.profile.api import _plane, _viewer
from sh_platform.profile.view import ADMIN, norm

log = logging.getLogger(__name__)
router = APIRouter()
KINDS = ("comment", "suggestion", "ambiguity")
DECISIONS = ("accepted", "declined", "answered")
MAX_TEXT = 2000


class NewComment(BaseModel):
    kind: str = "comment"
    text: str
    anonymous: bool = False


class Decision(BaseModel):
    state: str
    answer: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _open(request: Request, node_id: str):
    try:
        plane, viewer = _plane(request), _viewer(request)
    except PermissionError:
        raise HTTPException(403, "Your company space could not be opened. Please ask your administrator.") from None
    rebuild_if_dirty(plane)
    if not any(n["id"] == node_id and not n.get("restricted") for n in graph_for(plane, viewer)["nodes"]):
        raise HTTPException(404, "No such node")  # unknown, another company's, or a silhouette: the same answer
    return plane, viewer


def _owner(plane, node_id: str) -> str | None:
    doc = read_json_strict(plane.path("graph", "company.json"), dict) or {}
    names = {n["id"]: n["label"] for n in doc.get("nodes", [])}
    return next((names.get(e["to"]) for e in doc.get("edges", []) if e["from"] == node_id and e["type"] == "owned_by"), None)


def _steward_is(plane, viewer) -> bool:
    saved = read_json_strict(plane.path("graph", "steward.json"), dict) or {}
    if saved.get("account_id") and saved["account_id"] == viewer.account_id:
        return True
    if saved.get("name"):
        return norm(saved["name"]) == norm(viewer.name)
    heads = [p for p in store.load(plane).get("people", {}).values() if (p.get("is_head_of_data") or {}).get("value") is True]
    if heads:
        return any(norm((p.get("name") or {}).get("value")) == norm(viewer.name) for p in heads)
    return ADMIN in viewer.roles


def _may_decide(plane, viewer, node_id: str) -> bool:
    owner = _owner(plane, node_id)
    return bool(owner and norm(owner) == norm(viewer.name)) or _steward_is(plane, viewer)


def _read(plane) -> dict:
    return read_json_strict(plane.path("graph", "comments.json"), dict) or {}


def _add_version(plane, node_id: str, what: str, by: str, ref: str) -> None:
    path = plane.path("graph", "versions.json")
    with lock_for(path):
        doc = read_json_strict(path, dict) or {}
        rows = doc.setdefault(node_id, [])
        rows.append({"v": len(rows) + 1, "what": what, "by": by, "at": _now(), "ref": ref})
        write_json_atomic(path, doc)


def _first(name: str | None) -> str:
    return (name or "").split(" ")[0]


def _line(c: dict, owner: str | None, stew: str, became: dict) -> str:
    """The state line under a comment: who is to decide while open; who decided, in which capacity, and what it became."""
    if c["state"] == "open":
        who = owner or stew
        return f"Open · {_first(who)} to decide" if who else "Open"
    if c["state"] == "answered":
        return f"Answered: {c['answer']}" if c.get("answer") else "Answered"
    by = c.get("decided_by") or ""
    cap = " (steward)" if stew and norm(by) == norm(stew) else " (owner)" if owner and norm(by) == norm(owner) else ""
    head = f"{c['state'].capitalize()}{f' by {_first(by)}{cap}' if by else ''}"
    v = became.get(f"comment:{c['id']}") if c["state"] == "accepted" else None
    return head + (f" · became version {v}" if v else "") + (f": {c['answer']}" if c.get("answer") else "")


@router.get("/api/company/graph/node/{node_id}/comments")
def get_api_company_graph_node_node_id_comments(request: Request, node_id: str) -> dict:
    plane, viewer = _open(request, node_id)
    owner, stew = _owner(plane, node_id), steward(plane, request.app.state.account_store.in_company(request.state.company_id))
    became = {str(v.get("ref")): v.get("v") for v in (read_json_strict(plane.path("graph", "versions.json"), dict) or {}).get(node_id, [])}
    items = [{**c, "line": _line(c, owner, stew, became)} for c in _read(plane).get(node_id, [])]
    return {"comments": items, "may_decide": _may_decide(plane, viewer, node_id)}


@router.post("/api/company/graph/node/{node_id}/comments")
def post_api_company_graph_node_node_id_comments(request: Request, node_id: str, body: NewComment) -> dict:
    plane, viewer = _open(request, node_id)
    text = body.text.strip()
    if body.kind not in KINDS:
        raise HTTPException(400, "Choose comment, suggestion or ambiguity")
    if not text or len(text) > MAX_TEXT:
        raise HTTPException(400, "Write something, up to 2000 characters")
    item = {"id": secrets.token_hex(6), "kind": body.kind, "text": text, "by": "Anonymous" if body.anonymous else (viewer.name or "Anonymous"),
            "at": _now(), "state": "open", "decided_by": None, "decided_at": None, "answer": None}
    path = plane.path("graph", "comments.json")
    with lock_for(path):
        doc = _read(plane)
        doc.setdefault(node_id, []).append(item)
        write_json_atomic(path, doc)
    return item


@router.post("/api/company/graph/node/{node_id}/comments/{comment_id}/decide")
def post_api_company_graph_node_node_id_comments_comment_id_decide(request: Request, node_id: str, comment_id: str, body: Decision) -> dict:
    plane, viewer = _open(request, node_id)
    if not _may_decide(plane, viewer, node_id):
        raise HTTPException(403, "Only the owner or the map steward can decide this")
    if body.state not in DECISIONS:
        raise HTTPException(400, "Choose accepted, declined or answered")
    answer = (body.answer or "").strip() or None
    if body.state == "answered" and not answer:
        raise HTTPException(400, "Write the answer")
    path = plane.path("graph", "comments.json")
    with lock_for(path):
        doc = _read(plane)
        item = next((c for c in doc.get(node_id, []) if c["id"] == comment_id), None)
        if item is None:
            raise HTTPException(404, "No such comment")
        item.update(state=body.state, decided_by=viewer.name, decided_at=_now(), answer=answer)
        write_json_atomic(path, doc)
    if body.state == "accepted":
        _add_version(plane, node_id, f"Accepted: {item['text'][:120]}", viewer.name, f"comment:{comment_id}")  # the writer's name is never recorded
    return item
