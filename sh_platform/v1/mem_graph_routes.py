"""The context map for the Map page (MEM2a). Every role reads it, filtered by who the viewer is (their own talks and those of projects they may read).

- `GET /api/v1/memory/graph` -> {built_at, nodes: [{id, type, label, summary?}], edges: [{from, to, type}]}; a summary node carries its text, decisions,
  open questions, preferences learned, topics and its source (agent, when, how many turns); raw turns are never sent.
- `DELETE /api/v1/memory/summaries/{sid}` -> {forgotten: sid}; the person who had the talk forgets its summary, its vectors and its edges."""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import mem_graph as G
from sh_platform.v1 import mem_summary as S
from sh_platform.v1.mem_routes import CODES
from sh_platform.v1.p1_project import Refused
from sh_platform.v1.seats import viewer_of

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/v1/memory/graph")
def get_graph(request: Request):
    viewer, plane = viewer_of(request), _plane(request)
    try:
        v = G.view(plane, viewer)
        have = {s["id"]: s for s in S.visible_items(plane, viewer, latest_only=False)}
        for n in v["nodes"]:
            if n["type"] == "summary" and n["id"].split(":", 1)[1] in have:
                s = have[n["id"].split(":", 1)[1]]
                n["summary"] = {k: s[k] for k in ("text", "agent_name", "who", "at", "decisions", "open", "prefs", "topics", "source", "superseded")}
                n["summary"]["id"] = s["id"]
        return JSONResponse(v)
    except (OSError, ValueError):
        log.warning("the context map could not be read", exc_info=True)
        return JSONResponse({"error": "failed", "message": "The conversations map could not be opened. Please try again."}, status_code=500)


@router.delete("/api/v1/memory/summaries/{sid}")
def forget_summary(request: Request, sid: str):
    viewer, plane = viewer_of(request), _plane(request)
    try:
        S.forget(plane, viewer, sid)
        return JSONResponse({"forgotten": sid})
    except Refused as e:
        return JSONResponse({"error": CODES.get(e.status, "failed"), "message": e.message}, status_code=e.status)
