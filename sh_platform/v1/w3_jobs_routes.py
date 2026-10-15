"""W3: the jobs and events admin page, and the event stream.

- `GET /api/v1/jobs` -> {mode, stats, jobs, failed, events, runs} for the signed-in company (data engineer seat)
- `POST /api/v1/jobs/{id}/retry` -> {retried}   (a failed job goes back on the queue)
- `GET /api/v1/events/stream?after=<id>` -> server-sent events for job progress and Action badges of the signed-in company. The stream ends
  after about 25 s on purpose; the screen reconnects with the last id it saw (ui/src/live/useLive.ts does).
"""
import asyncio
import json
import time

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse

from sh_platform import events, jobs, mode
from sh_platform.v1.seats import CONSUMER, DATA_ENGINEER, require_seat

router = APIRouter()
BASE = "/api/v1/jobs"
STREAM_S = 25.0  # a stream ends after this long; the screen reconnects
SHOWN = ("id", "name", "state", "tries", "max_tries", "error", "queued_at", "started_at", "finished_at")


def _mine(request: Request, rows: list[dict]) -> list[dict]:
    cid = request.state.company_id
    return [{k: r.get(k) for k in SHOWN} for r in rows if r.get("company_id") == cid]


def _runs(request: Request) -> list[dict]:
    """V6 (walk gap 14): pipeline runs of this company's projects, newest first. In simple mode a run happens inside the server, not on the queue,
    so the queue never lists it; each project's own run log (build/<project>/runs.jsonl) does."""
    try:
        from sh_platform.profile.api import _plane
        from sh_platform.v1 import b6_run, p1_project
        plane = _plane(request)
        out = [{"project_id": p["id"], "title": p.get("title"), "run_id": r.get("run_id"), "mode": r.get("mode") or "sandbox", "status": r.get("status"),
                "started": r.get("started"), "finished": r.get("finished")}
               for p in p1_project.all_projects(plane) for r in b6_run.runs(plane, p["id"], 5)]
        return sorted(out, key=lambda r: str(r["started"] or ""), reverse=True)[:30]
    except Exception:  # noqa: BLE001 - the page lists the queue even when a project's run log cannot be read
        return []


@router.get(BASE)
def listing(request: Request):
    require_seat(request, DATA_ENGINEER)
    q, cid = jobs.queue(), request.state.company_id
    evs = [e for e in events.bus().since(max(0, events.bus().latest() - 60), 60) if (e["payload"] or {}).get("company_id") == cid]
    mine = _mine(request, q.recent(200))
    return {"mode": mode.mode(), "stats": {s: sum(1 for j in mine if j["state"] == s) for s in ("queued", "running", "retrying", "done", "failed")},
            "jobs": mine[:50], "failed": _mine(request, q.failed(200))[:50], "events": evs[-30:][::-1], "runs": _runs(request)}


@router.post(BASE + "/{jid}/retry")
def retry(jid: str, request: Request):
    require_seat(request, DATA_ENGINEER)
    rec = jobs.queue().get(jid)
    if not rec or rec.get("company_id") != request.state.company_id:
        return JSONResponse({"detail": {"error": "not_found", "message": "There is no such job."}}, status_code=404)
    if not jobs.queue().retry(jid):
        return JSONResponse({"detail": {"error": "invalid", "message": "Only a failed job can be sent again."}}, status_code=409)
    return {"retried": jid}


@router.get("/api/v1/events/stream")
def stream(request: Request, after: int | None = None):
    require_seat(request, CONSUMER)
    cid, latest = request.state.company_id, events.bus().latest()
    start = latest if after is None or after > latest else max(0, after)  # an id from before a restart is ahead of the new count

    async def gen():  # async: a waiting stream must not hold one of the server's worker threads for 25 s
        yield "retry: 2000\n\n"
        end, last, mine = time.monotonic() + STREAM_S, start, []
        while not mine and time.monotonic() < end and not await request.is_disconnected():
            got = await run_in_threadpool(events.bus().since, last)
            last = got[-1]["id"] if got else last  # other companies' events are skipped, never waited on again
            mine = [ev for ev in got if (ev["payload"] or {}).get("company_id") == cid]
            if not mine:
                await asyncio.sleep(1)
        for ev in mine:
            yield f"id: {ev['id']}\ndata: {json.dumps(ev, default=str)}\n\n"
        yield ": end\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
