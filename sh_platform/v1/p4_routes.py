"""P4 Benchmarks: GET /api/v1/build/{iid}/benchmarks reads the design's benchmarks, Flow's last check and why the build pack cannot be
signed yet; POST /api/v1/build/{iid}/pack/sign signs the build pack (refused while a miss has no answered comment). Logic: p4_benchmarks."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from sh_platform.build import runner
from sh_platform.v1 import p4_benchmarks as P4
from sh_platform.v1.b4_load import IID

router = APIRouter()


def _iid(iid: str) -> str:
    if not IID.fullmatch(iid):
        raise HTTPException(404, "There is no such intent.")
    return iid


@router.get("/api/v1/build/{iid}/benchmarks")
def get_benchmarks(request: Request, iid: str):
    plane, _ = runner._company(request)
    sow = P4._read(plane.path("intents", _iid(iid), "sow.json"))
    return {"intent_id": iid, "benchmarks": P4.for_design(sow), "verify": P4._read(plane.path("build", "verify", f"{iid}.json"), list),
            "sign_block": P4.sign_block(plane, iid)}


@router.post("/api/v1/build/{iid}/pack/sign")
def post_sign(request: Request, iid: str):
    plane, viewer = runner._company(request)
    try:
        return {"project": P4.sign(plane, _iid(iid), viewer.name)}
    except ValueError as e:
        raise HTTPException(409, str(e)) from None
    except Exception as e:  # P1's Refused carries its own status and sentence
        if hasattr(e, "status") and hasattr(e, "message"):
            raise HTTPException(e.status, e.message) from None
        raise
