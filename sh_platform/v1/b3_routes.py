"""B3 Mapping sheet routes. Reads for the working seats; drafting and editing for the architect (analyst, company admin), checked again
here through sh_platform.v1.seats so a widened yaml never lets another seat write. A switched-off Build centre is refused as the Build
routes do (build.agents.routes._switched_on)."""
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response

from sh_platform.build.agents import runtime as R
from sh_platform.build.agents.routes import _switched_on
from sh_platform.profile.api import _plane
from sh_platform.v1 import b3_mapping as M
from sh_platform.v1.seats import ARCHITECT, require_seat

router = APIRouter()
BASE = "/api/v1/build/{iid}/mapping"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": code, "message": message}, status_code=status)


def _plane_or_err(request: Request):
    if not _switched_on(request):
        return None, _err(403, "build_off", "The Build centre is switched off for this company.")
    try:
        return _plane(request), None
    except PermissionError:
        return None, _err(403, "forbidden", "This company space cannot be opened.")


def _answer(fn):
    try:
        return fn()
    except M.NotFound as e:
        return _err(404, "not_found", str(e))
    except M.Refusal as e:
        return _err(409, "refused", str(e))


@router.get(BASE)
def get_mapping(request: Request, iid: str):
    plane, err = _plane_or_err(request)
    if err:
        return err

    def work():
        got = M.read(plane, iid)
        if got is None:
            raise M.NotFound("There is no mapping sheet for this intent yet.")
        return got
    return _answer(work)


@router.post(BASE)
async def post_mapping(request: Request, iid: str):
    viewer = require_seat(request, ARCHITECT)
    plane, err = _plane_or_err(request)
    if err:
        return err
    rt = R.runtime_for_request(request, plane, viewer)
    return await run_in_threadpool(_answer, lambda: M.draft(plane, iid, rt))


@router.put(BASE + "/rows/{n}")
async def put_row(request: Request, iid: str, n: str):
    require_seat(request, ARCHITECT)
    plane, err = _plane_or_err(request)
    if err:
        return err
    try:
        body = await request.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        return _err(422, "refused", "Send the changed cells as an object.")
    if not n.isdigit():
        return _err(404, "not_found", "No such row.")
    return _answer(lambda: {"row": M.edit_row(plane, iid, int(n), body)})


@router.get("/api/v1/build/{iid}/mapping.xlsx")
def get_xlsx(request: Request, iid: str):
    plane, err = _plane_or_err(request)
    if err:
        return err

    def work():
        got = M.read(plane, iid)
        if got is None:
            raise M.NotFound("There is no mapping sheet for this intent yet.")
        return Response(M.xlsx(got["sheet"]), media_type=XLSX,
                        headers={"Content-Disposition": f'attachment; filename="mapping-{iid}-v{got["sheet"].get("version", 1)}.xlsx"'})
    return _answer(work)
