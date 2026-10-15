"""The job handlers. Each takes a JSON payload {data_root, company_id, ...} and returns a JSON-able result.

A pipeline run that the rules refuse (Refused) is a result, not a failure: retrying cannot fix it. `run_pipeline` turns it back into the
Refused the route expects, so a screen sees the same words in both modes.
"""
from __future__ import annotations

from datetime import datetime

from sh_platform import mode as _mode
from sh_platform.jobs import job, queue
from sh_platform.plane import PlaneStore


def _plane(p: dict):
    return PlaneStore(p["data_root"]).plane_for(p["company_id"])


def payload_of(plane, **more) -> dict:
    return {"data_root": str(plane.root.parent), "company_id": plane.company_id, **more}


def _json(x):
    import json
    return json.loads(json.dumps(x, default=str))


@job("b6.tick")
def b6_tick(p: dict):
    from sh_platform.v1 import b6_schedule
    now = datetime.fromisoformat(p["now"]) if p.get("now") else None
    return _json(b6_schedule.tick(_plane(p), now))


@job("b6.on_arrival")
def b6_on_arrival(p: dict):
    from sh_platform.v1 import b6_schedule
    return _json(b6_schedule.on_arrival(_plane(p), p["source_code"]))


@job("b6.run")
def b6_run(p: dict):
    from sh_platform.v1 import b6_plan as B, b6_run as R
    try:
        plan = B.get(_plane(p), p["pid"], p["version"]) if p.get("version") else None  # V6: the builder runs the approved pack version, not a newer draft
        return {"run": _json(R.run(_plane(p), p["pid"], p.get("mode", "sandbox"), plan=plan, by=p.get("by"), trigger=p.get("trigger", "manual"), job_id=p.get("_job_id")))}
    except R.Refused as e:
        return {"refused": {"message": e.message, "status": e.status}}


@job("d1.tick")
def d1_tick(p: dict):
    from sh_platform.v1 import d1_delivery
    return _json(d1_delivery.tick(_plane(p)))


@job("graph.rebuild")
def graph_rebuild(p: dict):
    from sh_platform.graph import hooks
    hooks._rebuild_now(_plane(p))
    return {"rebuilt": p["company_id"]}


def run_pipeline(plane, pid: str, mode: str, by: str | None, version: int | None = None) -> dict:
    """A pipeline run through the queue; waits for the record. Simple mode runs it here (the old behaviour); production runs it on a worker."""
    from sh_platform.jobs import JobFailed
    from sh_platform.v1 import b6_run as R
    try:
        res = queue().call("b6.run", payload_of(plane, pid=pid, mode=mode, by=by, version=version), key=f"b6.run:{plane.company_id}:{pid}", tries=1)
    except JobFailed as e:  # production: the worker's error stays in the job record (Settings, Jobs and events); the screen gets plain words
        if str(e) == "the same job is already waiting":
            raise R.Refused("This pipeline is already running. Wait for it to finish.", 409) from None
        raise R.Refused("The pipeline run could not finish. Try again in a minute; the data team can see why under Jobs and events.", 503) from None
    if "refused" in res:
        raise R.Refused(res["refused"]["message"], res["refused"]["status"])
    return res["run"]


def minute_key(name: str, plane) -> str:
    return f"{name}:{plane.company_id}:{datetime.now().strftime('%Y%m%d%H%M')}"
