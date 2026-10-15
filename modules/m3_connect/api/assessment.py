"""Module 3 scaffold: list, start and read an assessment. Starts from the newest signed baseline, read by path (domain/inputs.py).
The company and the person come from the server session, never from a body."""
import functools

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from modules.m3_connect.domain import inputs as I
from modules.m3_connect.domain.steps import steps_for
from modules.m3_connect.store import assessment as A
from sh_platform.plane import CrossCompanyError, PlaneStore

router = APIRouter()
NO_SPACE = "Your company space could not be opened. Please ask your administrator."
NOT_FOUND = "We could not find that assessment."


def plain(status: int, error: str, message: str) -> JSONResponse:
    return JSONResponse({"error": error, "message": message}, status_code=status)


def _plane(request: Request):
    return PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()


def _viewer(request: Request) -> I.Viewer:
    st = request.app.state
    name = str((st.account_store.get(request.state.account_id) or {}).get("display_name") or "")
    twins = [a for a in st.account_store.in_company(request.state.company_id) if I._norm(a.get("display_name")) == I._norm(name)]
    return I.Viewer(name, frozenset(request.state.roles or []), len(twins) > 1)


def guarded(fn):
    """Route decorator: the module's failures become plain answers; nothing technical reaches the screen."""
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except A.NoSignedBaseline as e:
            return plain(409, "no_baseline", str(e))
        except (I.InputsUnreadable, A.StoreError) as e:
            return plain(500, "unreadable", str(e))
        except (PermissionError, CrossCompanyError):
            return plain(403, "forbidden", NO_SPACE)
    return inner


def _label(outcome: dict | None) -> str:
    """A baseline told apart by its own name, else by the day it was signed."""
    o = outcome or {}
    return str(o.get("title") or o.get("name") or "").strip() or f"Baseline signed {str(o.get('signed_at') or '')[:10]}".strip()


@router.get("/assessments")
@guarded
def list_assessments(request: Request):
    plane = _plane(request)
    latest = I.latest_signed_baseline(plane)
    rows = A.assessments(plane)
    labels: dict[str, str] = {}
    for a in rows:
        bid = a["baseline_outcome_id"]
        if bid not in labels:
            labels[bid] = _label(I.read_baseline_outcome(plane, bid))
    return {"assessments": [{**a, "baseline_label": labels[a["baseline_outcome_id"]]} for a in rows],
            "signed_baseline": latest is not None,
            "can_start": latest is not None and all(a["baseline_outcome_id"] != latest["outcome_id"] for a in rows),
            "baseline_label": _label(latest) if latest else ""}


@router.post("/assessments")
@guarded
def create_assessment(request: Request):
    plane = _plane(request)
    made, created = A.create(plane, I.latest_signed_baseline(plane), _viewer(request).name)
    return JSONResponse({"assessment": made}, status_code=201 if created else 200)


@router.get("/assessments/{assessment_id}")
@guarded
def get_assessment(assessment_id: str, request: Request):
    plane = _plane(request)
    a = A.read_assessment(plane, assessment_id)
    if a is None:
        return plain(404, "not_found", NOT_FOUND)
    baseline = I.read_baseline_outcome(plane, a["baseline_outcome_id"])
    inputs = I.read_inputs(plane, baseline, a["charter_outcome_id"], _viewer(request)) if baseline else None
    return {"assessment": a, "steps": steps_for(A.folder(plane, assessment_id)), "inputs": inputs}
