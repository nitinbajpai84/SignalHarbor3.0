"""B5 Ops and Loaded. Per source: the last run, rows, on time / late / failed / not arrived (the 2.0 ops read, sh_platform/build/ops.py,
slimmed to warehouse/runs.json alone so a company with no pipeline contracts still sees its runs). Alerts keep their state through the
kernel store (sh_platform/build/alerts.py); a newly opened one is posted to the room of every intent that uses the source.
The ops manager's act: build/ops/loaded.json {"periods": [{"period", "source_id", "state", "reason", "by", "at"}]}."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

from sh_platform.build import alerts as store_alerts
from sh_platform.build.ops import _ask, _day
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
PERIOD = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
STATES = {"loaded", "not_loaded"}


def _read(path, default):
    try:
        data = read_json_strict(path, dict)
    except (OSError, ValueError) as e:
        log.warning("%s unreadable: %s", path.name, type(e).__name__)
        return default
    return data if data is not None else default


def _runs(plane) -> list[dict]:
    return [r for r in _read(plane.path("warehouse", "runs.json"), {}).get("runs") or [] if isinstance(r, dict) and r.get("source")]


def _state(run: dict | None) -> str:
    if run is None:
        return "missing"
    if run.get("status") == "failed" or run.get("schema_ok") is False:
        return "failed"
    return "late" if run.get("status") == "late" or not run.get("on_time") else "on_time"


def _intents_using(plane, source: str) -> list[str]:
    out = []
    for f in sorted(plane.path("intents").glob("*/sow.json")):
        sow = _read(f, {})
        if any(source in {s.get("id"), s.get("name")} for s in sow.get("sources") or [] if isinstance(s, dict)):
            out.append(f.parent.name)
    return out


def _to_room(plane, source: str, text: str, ref: dict) -> None:
    """Guarded: a missing or broken room never breaks ops."""
    try:
        from sh_platform.v1.room import post
    except ImportError:
        return
    for iid in _intents_using(plane, source):
        try:
            post(plane, iid, "watcher", "note", text, to=["flow", "people"], refs=[ref])
        except Exception:  # noqa: BLE001 - the room is someone else's card
            log.warning("room post failed for %s", iid, exc_info=True)


def loaded(plane) -> list[dict]:
    return [p for p in _read(plane.path("build", "ops", "loaded.json"), {}).get("periods") or [] if isinstance(p, dict)]


def default_period(day: date) -> str:
    """The month the ops manager confirms: the one before the report day."""
    y, m = (day.year, day.month - 1) if day.month > 1 else (day.year - 1, 12)
    return f"{y}-{m:02d}"


def summary(plane, today: date) -> dict:
    runs = _runs(plane)
    days = {d for r in runs if (d := _day(r.get("started"))) and d <= today}
    if days and today not in days:  # report on the latest day that has runs
        today = max(days)
    named = set()
    for f in sorted(plane.path("intents").glob("*/sow.json")):
        named |= {str(s.get("id")) for s in (_read(f, {}).get("sources") or []) if isinstance(s, dict) and s.get("id")}
        named |= {str(s.get("name")) for s in (_read(f, {}).get("sources") or []) if isinstance(s, dict) and s.get("name")}
    sources = [s for s in dict.fromkeys(r["source"] for r in runs) if s.removeprefix("v1_").split("__")[0] in named or s in named]
    rows, derived, refs = [], [], {}
    for s in sources:
        mine = [r for r in runs if r["source"] == s]
        got = next((r for r in reversed(mine) if _day(r.get("ended") or r.get("started")) == today), None)
        last = got or mine[-1]
        state, owner = _state(got), last.get("owner")
        rows.append({"source_id": s.removeprefix("v1_").split("__")[0], "run_source": s, "owner": owner, "state": state, "last_run": last.get("id"),
                     "arrived": last.get("ended"), "rows": last.get("rows")})
        if state != "on_time":
            what = {"missing": "the file has not arrived", "late": "the file arrived late", "failed": "today's run failed its checks"}[state]
            derived.append({"id": f"{s}:{state}", "kind": state, "source": s, "measure": None, "owner": owner, "ask": _ask(owner or "team", s, what)})
            refs[f"{s}:{state}"] = {"kind": "run", "id": last.get("id")}
    before = {a.get("id") for a in store_alerts._read(plane)}
    kept = store_alerts.sync(plane, derived, today.isoformat())
    asks = {d["id"]: d["ask"] for d in derived}
    for d in derived:
        if d["id"] not in before:
            _to_room(plane, d["source"], f"Watcher: {d['source']} is {d['kind'].replace('_', ' ')} on {today.isoformat()}. {d['ask']}", refs[d["id"]])
    alerts = [{**a, "ask": asks.get(a["id"])} for a in kept if a.get("state") != "closed"]
    try:  # P5: daily state per live project, Watcher tickets
        from sh_platform.v1.p5_handover import after_ops; after_ops(plane, today, rows)
    except Exception:  # noqa: BLE001 - P5 never takes the ops page down
        log.warning("P5 after_ops failed", exc_info=True)
    return {"date": today.isoformat(), "period": default_period(today), "sources": rows, "alerts": alerts, "loaded": loaded(plane)}


def mark(plane, body: dict, by: str) -> dict:
    """Upsert one Loaded / Not loaded act per period and source. Raises ValueError on a bad body."""
    period, source, state = body.get("period"), body.get("source_id"), body.get("state")
    reason = (body.get("reason") or "").strip()[:500] if isinstance(body.get("reason"), str) else ""
    if not isinstance(period, str) or not PERIOD.match(period):
        raise ValueError("period must be YYYY-MM")
    if not isinstance(source, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", source):
        raise ValueError("source_id is not valid")
    if state not in STATES:
        raise ValueError("state must be loaded or not_loaded")
    if state == "not_loaded" and not reason:
        raise ValueError("say why it is not loaded")
    rec = {"period": period, "source_id": source, "state": state, "reason": reason or None, "by": by, "at": datetime.now(timezone.utc).isoformat()}
    path = plane.path("build", "ops", "loaded.json")
    with lock_for(path):
        items = [p for p in loaded(plane) if (p.get("period"), p.get("source_id")) != (period, source)]
        write_json_atomic(path, {"periods": [*items, rec]})
        try:  # the company map follows every write that changes what it shows
            from sh_platform.v1.m1_map import touch; touch(plane)
        except ImportError:
            pass
    word = "Loaded" if state == "loaded" else f"Not loaded ({reason})"
    _to_room(plane, source, f"{by} marked {source} for {period}: {word}.", {"kind": "loaded", "id": f"{period}:{source}"})
    return rec
