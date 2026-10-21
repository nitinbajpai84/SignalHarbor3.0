"""Harbor 3.0 public API (logic in v3_public_api; examples in docs/v3/API.md). Failures answer {error, message}.
Public, under /api/public/v1, with `Authorization: Bearer shpub...`: GET /figures, GET /figures/{id}, POST /ask {text}, GET /signals?status=, GET /documents, GET /openapi.json.
Office admin (signed in), under /api/v3/api-keys: list, make, revoke a key; set or clear its webhook; read its calls."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field

from sh_platform.profile.api import _plane
from sh_platform.v1 import v3_public_api as A

router = APIRouter()
pub = APIRouter(prefix="/api/public/v1", dependencies=[Depends(HTTPBearer(auto_error=False, description="shpub.<company>.<id>.<secret>"))])


class AskIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000, description="The question, in plain words.")


@pub.get("/figures", summary="The office's figures", tags=["figures"])
def figures(ctx: A.Ctx = Depends(A.gate("figures"))):
    return {"figures": A.figures(ctx)}


@pub.get("/figures/{figure_id}", summary="One figure with its receipts", tags=["figures"])
def figure(figure_id: str, ctx: A.Ctx = Depends(A.gate("figures"))):
    return A.figure(ctx, figure_id)


@pub.post("/ask", summary="Ask a question; the answer comes with its figure and trace", tags=["ask"])
def ask(body: AskIn, ctx: A.Ctx = Depends(A.gate("ask"))):
    if ctx.rec["entity_ids"]:
        raise HTTPException(403, {"error": "scope_not_granted", "message": "A key limited to some entities cannot ask."})
    return A.ask(ctx, body.text.strip())


@pub.get("/signals", summary="Signals that have fired", tags=["signals"])
def signals(status: str | None = None, ctx: A.Ctx = Depends(A.gate("signals"))):
    return {"signals": A.signals(ctx, status)}


@pub.get("/documents", summary="Documents: metadata only, never the file", tags=["documents"])
def documents(ctx: A.Ctx = Depends(A.gate("documents"))):
    return {"documents": A.documents(ctx)}


@pub.get("/openapi.json", include_in_schema=False)
def openapi(request: Request):
    return get_openapi(title="Signal Harbor public API", version="1.0", description="Read-only. Send `Authorization: Bearer <key>`. Keys are made on the Build page.",
                       routes=[r for r in pub.routes if getattr(r, "include_in_schema", True)])


router.include_router(pub)


# ---- the office admin's page ----------------------------------------------------------------------------------------------------------------

def _body(data):
    return data if isinstance(data, dict) else {}


def _admin(request: Request) -> str:
    me = request.app.state.account_store.get(request.state.account_id) or {}
    return str(me.get("display_name") or "")


@router.get("/api/v3/api-keys")
def list_keys(request: Request):
    plane = _plane(request)
    return {"keys": A.listing(plane), "scopes": list(A.SCOPES), "calls": A.calls(plane, limit=20)}


@router.post("/api/v3/api-keys")
async def make_key(request: Request):
    plane = _plane(request)
    try:
        b = _body(await request.json())
    except ValueError:
        b = {}
    try:
        return A.issue(plane, _admin(request), b.get("label"), b.get("scopes") or [], b.get("entity_ids"), b.get("kind") or "company", b.get("member"),
                       b.get("rate_per_min", A.DEFAULT_RATE))
    except A.KeyError_ as e:
        raise HTTPException(400, str(e)) from None


@router.delete("/api/v3/api-keys/{key_id}")
def revoke_key(key_id: str, request: Request):
    if not A.revoke(_plane(request), key_id):
        raise HTTPException(404, "I cannot find that key.")
    return {"revoked": True}


@router.get("/api/v3/api-keys/{key_id}/calls")
def key_calls(key_id: str, request: Request):
    return {"calls": A.calls(_plane(request), key_id, 100)}


@router.post("/api/v3/api-keys/{key_id}/webhook")
async def set_hook(key_id: str, request: Request):
    try:
        b = _body(await request.json())
    except ValueError:
        b = {}
    try:
        return A.set_webhook(_plane(request), key_id, str(b.get("url") or ""))
    except A.KeyError_ as e:
        raise HTTPException(400, str(e)) from None


@router.delete("/api/v3/api-keys/{key_id}/webhook")
def clear_hook(key_id: str, request: Request):
    if not A.clear_webhook(_plane(request), key_id):
        raise HTTPException(404, "That key has no webhook.")
    return {"cleared": True}
