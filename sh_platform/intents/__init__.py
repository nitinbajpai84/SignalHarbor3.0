"""Intent Centre v2: one router module per build card (docs/plan/INTENT-CENTRE-V2-BUILD-PLAN.md section 1).

Handlers open the company plane and the viewer with _plane(request) and _viewer(request), as sh_platform/outcomes.py does.
"""
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane, _viewer  # noqa: F401  re-exported for the card modules


def not_yet(spec: str) -> JSONResponse:
    """The stub answer until a card lands: 501 naming the spec file it waits for."""
    return JSONResponse({"detail": "Not available yet", "spec": spec}, status_code=501)
