"""E2b routes: the intake agent's extracted fields.

- `GET /api/v1/evidence/documents/{doc_id}/fields` → {fields}  ·  `POST .../extract` → {fields, exception_id} (reads the document if not yet read)
- `POST /api/v1/evidence/fields/{id}/confirm` · `/correct` {value} · `/reject` {reason?} → the field in the screen's shape {id, field, original, amended, confidence, state, page, line} plus {valuation_id, exception_id}
Logic: e2_extract."""
from fastapi import APIRouter, Body, Request

from sh_platform.profile.api import _plane
from sh_platform.v1 import e2_extract as X
from sh_platform.v1 import e2_screen as S
from sh_platform.v1.i2_north import Refused
from sh_platform.v1.i2_routes import _answer
from sh_platform.v1.seats import viewer_of

router = APIRouter()
BASE = "/api/v1/evidence"


def _do(request: Request, fn):
    viewer = viewer_of(request)
    plane = _plane(request)
    return _answer(lambda: fn(plane, viewer))


@router.get(BASE + "/documents/{doc_id}/fields")
def get_fields(request: Request, doc_id: str):
    return _do(request, lambda p, v: (S.check(p, v, doc_id), {"fields": X.fields_of(p, doc_id)})[1])


@router.post(BASE + "/documents/{doc_id}/extract")
def post_extract(request: Request, doc_id: str):
    def go(p, v):
        S.check(p, v, doc_id)
        got = X.read_document(p, doc_id, v)
        return {"fields": X.fields_of(p, doc_id), "exception_id": got["exception_id"]}
    return _do(request, go)


def _decided(p, field_id: str, done: dict) -> dict:
    """The screen's field after a decision, with the ids the revision flow produced beside it."""
    return {**S.field_view(p, field_id), "valuation_id": done.get("valuation_id"), "exception_id": done.get("exception_id")}


@router.post(BASE + "/fields/{field_id}/confirm")
def post_confirm(request: Request, field_id: str):
    return _do(request, lambda p, v: _decided(p, field_id, X.confirm(p, field_id, v)))


@router.post(BASE + "/fields/{field_id}/correct")
def post_correct(request: Request, field_id: str, body: dict = Body(default_factory=dict)):
    def go(p, v):
        if body.get("value") in (None, ""):
            raise Refused(422, "Type the corrected value.")
        return _decided(p, field_id, X.confirm(p, field_id, v, body["value"]))
    return _do(request, go)


@router.post(BASE + "/fields/{field_id}/reject")
def post_reject(request: Request, field_id: str, body: dict = Body(default_factory=dict)):
    return _do(request, lambda p, v: _decided(p, field_id, X.reject(p, field_id, v, str(body.get("reason") or ""))))
