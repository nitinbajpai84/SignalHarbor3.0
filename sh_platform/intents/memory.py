"""Memory in the intents (spec 46): North's opening line from what it remembers about the signed-in person. The memory lines themselves
are read, corrected and deleted through /api/memory/me/{agent} (sh_platform/memory/api.py); closure writes them (memory_close.py)."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.intents import _plane, _viewer, north

router = APIRouter()


@router.get("/api/intents/opening-line")
def get_intents_opening_line(request: Request):
    """`{line, preference, type, entry_ids}`, or `{line: null}` when North remembers nothing: the screen then says nothing about memory."""
    try:
        out = north.memory_opening(_plane(request), _viewer(request), request.query_params.get("type") or None)
    except PermissionError:
        return JSONResponse({"error": "forbidden", "message": "You do not have access to this."}, status_code=403)
    return out or {"line": None}
