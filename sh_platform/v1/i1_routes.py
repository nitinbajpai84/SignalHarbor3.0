"""I1 Company page routes. Reads for the company's working seats; edits and uploads for the decision maker (company admin, sponsor),
checked again here so a widened yaml never lets an analyst write. The company and the person come from the session only."""
import base64
import binascii

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.context_docs.api import MAX_BODY, _json_body, _plain
from sh_platform.profile.api import _answer, _name, _plane, _viewer
from sh_platform.v1 import i1_company

router = APIRouter()
EDITORS = frozenset({"company_admin", "sponsor"})


def _may_edit(request: Request) -> bool:
    return bool(EDITORS & set(request.state.roles or []))


def _refused(fn):
    try:
        return _answer(fn)
    except i1_company.Refusal as e:
        return _plain(422, "refused", str(e))


def _not_yours() -> JSONResponse:
    return _plain(403, "forbidden", "Only the decision maker can change the company page.")


@router.get("/api/v1/company")
def get_company(request: Request):
    return _answer(lambda: {**i1_company.read(_plane(request), _viewer(request)), "can_edit": _may_edit(request)})


@router.put("/api/v1/company")
async def put_company(request: Request):
    if not _may_edit(request):
        return _not_yours()
    body = await _json_body(request, 256 * 1024)
    if isinstance(body, JSONResponse):
        return body

    def work():
        plane = _plane(request)
        i1_company.save(plane, _name(request) or "A team member", body)
        return {**i1_company.read(plane, _viewer(request)), "can_edit": True}
    return await run_in_threadpool(_refused, work)


@router.post("/api/v1/company/documents")
async def upload_document(request: Request):
    if not _may_edit(request):
        return _not_yours()
    body = await _json_body(request, MAX_BODY)
    if isinstance(body, JSONResponse):
        return body
    try:
        data = base64.b64decode(str(body.get("data", "")), validate=True)
    except (binascii.Error, ValueError):
        return _plain(400, "bad_request", "That file could not be read. Please try again.")
    return await run_in_threadpool(_answer, lambda: i1_company.upload(
        _plane(request), str(body.get("filename") or ""), data))
