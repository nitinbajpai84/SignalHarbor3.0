"""Module 3's opening state: how many signed baselines (module 2 outcome records) this company has to start from, and its assessments."""
from fastapi import APIRouter, Request

from modules.m3_connect.domain import inputs as I
from modules.m3_connect.store import assessment as A
from sh_platform.plane import PlaneStore

router = APIRouter()


@router.get("/status")
def status(request: Request) -> dict:
    plane = PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()
    return {"module": "m3_connect", "baselines": len(I.signed_baselines(plane)), "assessments": len(A.assessments(plane))}
