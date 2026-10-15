"""B3 route: `GET /api/v1/build/p/{pid}/diagram` → {project_id, version, state, layers, nodes, edges}. Needs read access to the project."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import b6_diagram as D
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import p1_project as P1
from sh_platform.v1.seats import viewer_of

router = APIRouter()


@router.get("/api/v1/build/p/{pid}/diagram")
def get_diagram(pid: str, request: Request):
    viewer = viewer_of(request)
    plane = _plane(request)
    try:
        G1.require(plane, viewer, pid, "read")
        return D.diagram(D.latest_plan(plane, pid), plane)
    except P1.Refused as e:
        return JSONResponse({"error": "not_allowed" if e.status == 403 else "not_found", "message": e.message}, status_code=e.status)
    except D.Missing as e:
        return JSONResponse({"error": "not_found", "message": str(e)}, status_code=404)
