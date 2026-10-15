"""RUN1: one run id for every run (test and production), so operations and data governance can see what each run did.
Lineage: source -> file batch (source_batches.id) -> source record -> bronze (_load_id) -> silver -> gold (run_id column).
Append-only JSONL per company: `ops/runs.jsonl` (a start line, then a finish line per run) and `ops/run_steps.jsonl`. Never deleted.
ponytail: JSONL works in simple and production modes with no migration; move to a warehouse table when the list outgrows a file scan."""
from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone

from sh_platform.jsonfile import lock_for

log = logging.getLogger(__name__)
MODES, TRIGGERS = ("test", "production"), ("manual", "schedule", "file_arrived", "connector", "rerun")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append(plane, name: str, rec: dict) -> None:
    f = plane.path("ops", name)
    with lock_for(f):
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, "a", encoding="utf-8") as h:
            h.write(json.dumps(rec, default=str) + "\n")


def _read(plane, name: str) -> list[dict]:
    f = plane.path("ops", name)
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue  # a torn last line never hides the rest
    return out


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("run-%Y%m%d-%H%M%S-") + secrets.token_hex(2)


def start_run(plane, kind: str, mode: str, trigger: str, who: str | None, plan_id: str | None = None, pack_version: int | None = None,
              job_id: str | None = None, run_id: str | None = None) -> str:
    """`who` is an account display name only. Never raises into the caller's run: a log failure is a warning."""
    run_id = run_id or new_run_id()
    try:
        _append(plane, "runs.jsonl", {"run_id": run_id, "kind": kind, "mode": mode if mode in MODES else "test", "trigger": trigger if trigger in TRIGGERS else "manual",
                                      "who": who or "system", "plan_id": plan_id, "pack_version": pack_version, "job_id": job_id, "started": _now(), "status": "running"})
    except OSError:
        log.warning("run log: could not start %s", run_id, exc_info=True)
    return run_id


def step(plane, run_id: str, name: str, layer: str | None, target: str | None, rows_in: int | None = None, inserted: int | None = None,
         rejected: int | None = None, checks_passed: int = 0, checks_failed: int = 0, error: str | None = None, **refs) -> None:
    """`refs`: lineage links such as batch_id, file_id, load_id."""
    try:
        _append(plane, "run_steps.jsonl", {"run_id": run_id, "name": name, "layer": layer, "target": target, "rows_in": rows_in, "inserted": inserted,
                                           "rejected": rejected, "checks_passed": checks_passed, "checks_failed": checks_failed, "error": error, "at": _now(), **refs})
    except OSError:
        log.warning("run log: could not write a step of %s", run_id, exc_info=True)


def finish(plane, run_id: str, status: str) -> None:
    try:
        _append(plane, "runs.jsonl", {"run_id": run_id, "finished": _now(), "status": status})
    except OSError:
        log.warning("run log: could not finish %s", run_id, exc_info=True)


def record(plane, kind: str, mode: str, trigger: str, who: str | None, steps: list[dict], status: str, **kw) -> str:
    """A whole run in one call, for code that only knows the outcome afterwards."""
    rid = start_run(plane, kind, mode, trigger, who, **kw)
    for s in steps:
        step(plane, rid, **s)
    finish(plane, rid, status)
    return rid


def _merged(plane) -> list[dict]:
    runs: dict[str, dict] = {}
    for r in _read(plane, "runs.jsonl"):
        runs.setdefault(r["run_id"], {}).update(r)
    out = list(runs.values())
    for r in out:
        a, b = r.get("started"), r.get("finished")
        r["seconds"] = round((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds()) if a and b else None
    return sorted(out[::-1], key=lambda r: r.get("started") or "", reverse=True)  # newest first; same-second ties keep the later append first


def list_runs(plane, mode: str | None = None, kind: str | None = None, limit: int = 100) -> list[dict]:
    return [r for r in _merged(plane) if (not mode or r["mode"] == mode) and (not kind or r["kind"] == kind)][:limit]


def get_run(plane, run_id: str) -> dict | None:
    r = next((r for r in _merged(plane) if r["run_id"] == run_id), None)
    return {**r, "steps": [s for s in _read(plane, "run_steps.jsonl") if s["run_id"] == run_id]} if r else None


def pipelines(plane, now: datetime | None = None) -> list[dict]:
    """One row per project whose pipeline is approved, built or live: its own newest production run (when, how long, status, checks from the steps)
    and the next run its schedule gives. Reads only plans and this run log."""
    from sh_platform.v1 import b6_run as R, b7_studio, p1_project
    now = now or datetime.now()
    runs = [r for r in _merged(plane) if r.get("kind") == "pipeline" and r.get("mode") == "production" and r.get("plan_id")]
    steps = _read(plane, "run_steps.jsonl")
    out = []
    titles = {p["id"]: p.get("title") for p in p1_project.all_projects(plane)}
    root = plane.path("build")
    for d in sorted(root.iterdir() if root.is_dir() else []):
        p = {"id": d.name, "title": titles.get(d.name)}
        try:
            plan = R.latest_plan(plane, p["id"], live=True)
        except Exception:  # noqa: BLE001 - one unreadable plan must not blank the list
            continue
        if not plan or plan.get("state") not in R.LIVE_OK:
            continue
        last = next((r for r in runs if r["plan_id"] == p["id"]), None)
        mine = [s for s in steps if last and s["run_id"] == last["run_id"]]
        nxt = b7_studio.next_slot(plan.get("schedule") or {}, now)
        out.append({"source": p["id"], "title": p.get("title") or p["id"], "owner": plan.get("proposed_by"),
                    "last_run": last and {"run_id": last["run_id"], "started": last["started"], "seconds": last.get("seconds"),
                                          "status": "ok" if last.get("status") == "ok" else "failed",
                                          "rules": [{"passed": True}] * sum(s.get("checks_passed") or 0 for s in mine) + [{"passed": False}] * sum(s.get("checks_failed") or 0 for s in mine)},
                    "next_run": nxt.astimezone().isoformat(timespec="minutes") if nxt else None, "schedule": (plan.get("schedule") or {}).get("freq")})
    return out
