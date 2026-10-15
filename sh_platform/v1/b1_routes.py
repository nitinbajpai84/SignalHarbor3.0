"""B1 routes: Span's design from the signed intent of work. POST drafts (architect seat: analyst or company admin); GET reads the
latest design note. The diagram itself is 2.0's GET /api/company/build/architecture."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.build.agents.runtime import runtime_for_request
from sh_platform.profile.api import _name, _plane, _viewer
from sh_platform.v1 import b1_design as B

router = APIRouter()
ARCHITECT = {"analyst", "company_admin"}  # seat table: architect


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": code, "message": message}, status_code=status)


@router.get("/api/v1/build/{iid}/design")
def get_design(request: Request, iid: str):
    try:
        plane, viewer = _plane(request), _viewer(request)
    except PermissionError:
        return _err(403, "forbidden", "This company space cannot be opened.")
    try:
        sow = B.read_sow(plane, iid)
    except B.Refused as e:
        return _err(e.status, e.code, e.message)
    return {"intent_id": iid, "sow_state": sow.get("state"), "title": sow.get("title"), "design": B.read_design(plane, iid),
            "can_draft": bool(ARCHITECT & set(viewer.roles)) and sow.get("state") == "signed"}


@router.post("/api/v1/build/{iid}/design")
def post_design(request: Request, iid: str):
    try:
        plane, viewer = _plane(request), _viewer(request)
    except PermissionError:
        return _err(403, "forbidden", "This company space cannot be opened.")
    if not ARCHITECT & set(viewer.roles):
        return _err(403, "forbidden", "Only the architect asks Span for the design.")
    try:
        return B.design(plane, runtime_for_request(request, plane, viewer), iid, _name(request) or "A team member")
    except B.Refused as e:
        return _err(e.status, e.code, e.message)
