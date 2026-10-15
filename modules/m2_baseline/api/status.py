"""Module 2's opening state: which signed charters (module 1 outcome records) this company has to start from."""
from fastapi import APIRouter, Request

from sh_platform.plane import PlaneStore

router = APIRouter()


@router.get("/status")
def status(request: Request) -> dict:
    plane = PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()
    folder = plane.path("intents", "m1_intent", "outcomes")
    outcomes = sorted(p.stem for p in folder.glob("*.json")) if folder.is_dir() else []
    return {"module": "m2_baseline", "charters": len(outcomes)}
