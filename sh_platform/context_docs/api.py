"""The routes for company context uploads (D-032). Ported from `webapp/backend/routers/agent_docs.py`.

Changed for this product: the company and the person always come from the signed-in session (the earlier `domain`
form field is gone); the file travels as base64 in a JSON body, so no multipart library is needed and the client
keeps its one JSON path; the owner-or-admin check is replaced by the route roles in route_permissions.yaml (company
admin uploads, changes, deletes and decides; other company members list). Every route is declared there (default deny).
"""
import base64
import binascii
import json

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.context_docs import reader
from sh_platform.context_docs.store import AGENTS, DocStore
from sh_platform.plane import CrossCompanyError, PlaneStore

router = APIRouter()
MAX_BODY = reader.MAX_UPLOAD_BYTES * 4 // 3 + 64 * 1024  # base64 grows a file by a third; the rest is the form fields


def _plain(status: int, error: str, message: str) -> JSONResponse:
    return JSONResponse({"error": error, "message": message}, status_code=status)


def _store(request: Request, slug: str) -> DocStore:
    """The store of the signed-in company's own plane."""
    if slug not in AGENTS:
        raise FileNotFoundError("no such agent")
    try:
        return DocStore(PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure())
    except (LookupError, CrossCompanyError, ValueError):
        raise PermissionError("no company space") from None


def _answer(fn):
    """Runs fn, turning the store's failures into plain answers; nothing technical reaches the screen."""
    try:
        return fn()
    except reader.Refusal as e:
        return _plain(e.status, "refused", str(e))
    except FileNotFoundError:
        return _plain(404, "not_found", "We could not find that.")
    except (PermissionError, CrossCompanyError):
        return _plain(403, "forbidden", "Your company space could not be opened. Please ask your administrator.")


async def _json_body(request: Request, limit: int) -> dict | JSONResponse:
    too_big = _plain(413, "too_big", f"That file is too large. The limit is {reader.MAX_UPLOAD_BYTES // 1_000_000} MB.")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        return too_big
    raw = bytearray()
    async for chunk in request.stream():
        raw += chunk
        if len(raw) > limit:
            return too_big
    try:
        body = json.loads(bytes(raw))
    except ValueError:
        body = None
    return body if isinstance(body, dict) else _plain(400, "bad_request", "That could not be read. Please try again.")


@router.post("/api/agents/{slug}/docs")
async def upload(request: Request, slug: str):
    body = await _json_body(request, MAX_BODY)
    if isinstance(body, JSONResponse):
        return body
    try:
        data = base64.b64decode(str(body.get("data", "")), validate=True)
    except (binascii.Error, ValueError):
        return _plain(400, "bad_request", "That file could not be read. Please try again.")
    text = {k: str(body.get(k) or "") for k in ("filename", "title", "description")}

    def work():
        return _store(request, slug).upload(slug, request.state.account_id, text["filename"], data,
                                            title=text["title"], description=text["description"],
                                            visibility=str(body.get("visibility") or "private"),
                                            restricted=body.get("restricted") is True)
    return await run_in_threadpool(_answer, work)


@router.get("/api/agents/{slug}/docs")
def list_docs(request: Request, slug: str):
    admin = "company_admin" in (request.state.roles or [])  # a restricted (pay, HR) document is listed to the admin alone: not even its title
    return _answer(lambda: {"agent": slug, "documents": [d for d in _store(request, slug).documents(slug) if admin or not d.get("restricted")],
                            "accepted": reader.allowed_extensions(),
                            "max_mb": reader.MAX_UPLOAD_BYTES // (1024 * 1024)})


@router.post("/api/agents/{slug}/docs/{doc_id}/visibility")
async def visibility(request: Request, slug: str, doc_id: str):
    body = await _json_body(request, 4096)
    if isinstance(body, JSONResponse):
        return body
    def work():
        store, doc = _store(request, slug), None
        if "restricted" in body:  # the same admin route also sets the restricted flag (pay and HR documents)
            doc = store.set_restricted(slug, doc_id, body["restricted"] is True)
        return store.set_visibility(slug, doc_id, str(body.get("visibility", ""))) if "visibility" in body or doc is None else doc
    return _answer(work)


@router.post("/api/agents/{slug}/docs/{doc_id}/publish-summary")
async def publish_summary(request: Request, slug: str, doc_id: str):
    """A short summary is the only part of a document that other agents may read."""
    body = await _json_body(request, 16 * 1024)
    if isinstance(body, JSONResponse):
        return body
    return _answer(lambda: _store(request, slug).publish_summary(slug, doc_id, str(body.get("summary", ""))))


@router.delete("/api/agents/{slug}/docs/{doc_id}")
def delete_doc(request: Request, slug: str, doc_id: str):
    return _answer(lambda: {"deleted": _store(request, slug).delete(slug, doc_id)})


@router.get("/api/agents/{slug}/pending-memories")
def pending_memories(request: Request, slug: str, status: str = "pending"):
    return _answer(lambda: {"agent": slug, "pending": _store(request, slug).list_pending(slug, status or None)})


@router.post("/api/agents/{slug}/pending-memories/{pending_id}/decide")
async def decide(request: Request, slug: str, pending_id: int):
    body = await _json_body(request, 16 * 1024)
    if isinstance(body, JSONResponse):
        return body
    edits = {k: str(body[k]) for k in ("subject", "content", "kind") if body.get(k)}
    return _answer(lambda: _store(request, slug).decide_pending(
        slug, pending_id, str(body.get("decision", "")), request.state.account_id, **edits))
