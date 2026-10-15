"""Module 3's router. One file per package area so parallel packages never edit the same file:
status.py and assessment.py (scaffold), then sources.py (M3-P01), intake.py (M3-P02), trial.py (M3-P03), plan.py (M3-P04).
Every route here must also be declared in manifest.yaml and sh_platform/route_permissions.yaml."""
from fastapi import APIRouter, Depends

from modules.m3_connect.api import assessment, intake, plan, sources, status
from modules.m3_connect.api import trial  # M3-P03
from modules.m3_connect.api.signed_guard import refuse_when_signed

router = APIRouter(dependencies=[Depends(refuse_when_signed)])  # a signed assessment refuses every write, whichever package owns the route (SHARED.md, Routes)
for part in (status, assessment, sources, intake, trial, plan):
    router.include_router(part.router)
