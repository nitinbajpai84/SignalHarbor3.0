"""One guard for "a signed assessment is read-only" (copied from module 2's api/signed_guard.py, idea and wording).

Once both people have signed the plan (plan.json `signed_at`, or assessment.json state "signed"), every write (anything but GET, HEAD, OPTIONS) on
/assessments/{assessment_id}/... answers 409 in plain words before the route runs, whichever package owns the route. Only the signing route stays open
(it answers for itself: already signed). When the state cannot be read the write is refused (fail closed); an id that is no assessment is left to the
route's own 404.

Two ways in, same rule:
- `refuse_when_signed`, a router-level dependency. `api/__init__.py` puts it on the module's router, so every package's route is covered with nothing to do.
  A dependency can only raise FastAPI's HTTPException, so its body is {"detail": {"error", "message"}}.
- `GuardedRouter`, an APIRouter whose routes answer with the screens' own shape {"error", "message"} (ui/src/api/client.ts reads that). A package that
  builds its router as `GuardedRouter()` gets the plain answer on its screens; the dependency is then never reached.
"""
from typing import Callable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from modules.m3_connect.domain import accept
from modules.m3_connect.domain.plan import PlanError
from modules.m3_connect.store import assessment as A
from sh_platform.plane import CrossCompanyError, PlaneStore

SAFE = ("GET", "HEAD", "OPTIONS")
OPEN_WRITES = ("/plan/sign",)
SIGNED = "This assessment is signed, so it can no longer be changed. A change needs a new assessment."
UNREADABLE = "This assessment could not be checked, so nothing was changed. Please try again."


def is_signed(plane, assessment_id) -> bool:
    """True when signed; raises PlanError / StoreError / OSError / ValueError when the state cannot be read; False for no such assessment."""
    folder = A.folder(plane, assessment_id)
    if folder is None:
        return False
    base = A.read_assessment(plane, assessment_id)
    return bool(base and base.get("state") == "signed") or accept.is_signed(folder)


def refusal(request: Request) -> dict | None:
    """{"error", "message"} when this request is a write on a signed (or unreadable) assessment, else None."""
    assessment_id = request.scope.get("path_params", {}).get("assessment_id")
    if not assessment_id or request.method in SAFE or request.url.path.endswith(OPEN_WRITES):
        return None
    try:
        plane = PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()
        return {"error": "signed", "message": SIGNED} if is_signed(plane, assessment_id) else None
    except (PlanError, A.StoreError, ValueError, OSError):
        return {"error": "unreadable", "message": UNREADABLE}
    except (LookupError, CrossCompanyError, AttributeError):
        return None  # no company space: the route gives its own answer


def refuse_when_signed(request: Request) -> None:
    """The router-level dependency: Router(dependencies=[Depends(refuse_when_signed)])."""
    got = refusal(request)
    if got:
        raise HTTPException(status_code=409, detail=got)


class SignedGuard(APIRoute):
    def get_route_handler(self) -> Callable:
        inner = super().get_route_handler()

        async def handler(request: Request):
            got = refusal(request)
            return JSONResponse(got, status_code=409) if got else await inner(request)
        return handler


class GuardedRouter(APIRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, route_class=SignedGuard, **kwargs)
